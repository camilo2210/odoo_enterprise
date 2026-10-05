from odoo import Command
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUSTaxReport(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('us')
    def setUpClass(cls):
        super().setUpClass()

        cls.report = cls.env.ref('l10n_us_account.tax_report')
        cls.california = cls.env.ref('base.state_us_5')
        cls.san_mateo = cls.env.ref('l10n_us.county_us_06081')

        # The San Mateo sales are taxed by three jurisdictions, gathered in a group of taxes.
        cls.tax_state = cls._create_jurisdiction_tax("CA State", 6.0)
        cls.tax_county = cls._create_jurisdiction_tax(
            "San Mateo County", 2.25, 'county', l10n_us_county_id=cls.san_mateo.id)
        cls.tax_special = cls._create_jurisdiction_tax("CA Special", 1.25, 'special')
        cls.tax_group = cls.env['account.tax'].create({
            'name': "San Mateo",
            'amount_type': 'group',
            'type_tax_use': 'sale',
            'children_tax_ids': [Command.set((cls.tax_state | cls.tax_county | cls.tax_special).ids)],
        })

        # The state jurisdiction also has 0% variants and a rate reduced to 4%.
        cls.tax_exempt, cls.tax_non_taxable, cls.tax_reduced = cls.env['account.tax'].create([
            {
                'name': "CA Exempt",
                'amount': 0.0,
                'type_tax_use': 'sale',
                'l10n_us_exempt_parent_tax_id': cls.tax_state.id,
            },
            {
                'name': "CA Non-Taxable",
                'amount': 0.0,
                'type_tax_use': 'sale',
                'l10n_us_nontaxable_parent_tax_id': cls.tax_state.id,
            },
            {
                'name': "CA State reduced to 4%",
                'amount': 4.0,
                'type_tax_use': 'sale',
                'l10n_us_nontaxable_parent_tax_id': cls.tax_state.id,
            },
        ])

        cls.cash_basis_account = cls.env['account.account'].create({
            'name': "Cash Basis Transition",
            'code': 'cash.basis.transition',
            'account_type': 'income',
        })

    @classmethod
    def _create_jurisdiction_tax(cls, name, amount, jurisdiction_type='state', **values):
        return cls.env['account.tax'].create({
            'name': name,
            'amount': amount,
            'type_tax_use': 'sale',
            'l10n_us_jurisdiction_type': jurisdiction_type,
            'l10n_us_state_id': cls.california.id,
            **values,
        })

    def _create_invoice_and_options(self, *taxes):
        """ Invoice one $100 line per tax. A jurisdiction without activity is left out of the
        report, so only the invoiced taxes show up. The states are unfolded to assert their taxes. """
        self.invoice = self._create_invoice(
            invoice_date='2026-05-11',
            partner_id=self.partner_a,
            invoice_line_ids=[self._prepare_invoice_line(price_unit=100.0, tax_ids=tax) for tax in taxes],
            post=True,
        )
        self.options = self._generate_options(self.report, '2026-01-01', '2026-12-31', default_options={'unfold_all': True})

    def _base_lines(self, taxes):
        return self.invoice.line_ids.filtered(lambda line: line.display_type == 'product' and line.tax_ids & taxes)

    def _get_line_id(self, tax):
        """ Return the report line id of the row reporting 'tax'."""
        return next(
            line.id
            for line in self.report._get_lines(self.options)
            if self.report._get_model_info_from_id(line.id) == ('account.tax', tax.id)
        )

    def _audit_cell(self, tax, label):
        """ Return the move lines behind the cell of 'tax' for the 'label' column."""
        action = self.report.dispatch_report_action(self.options, 'action_audit_cell', {
            'report_line_id': None,
            'calling_line_dict_id': self._get_line_id(tax),
            'expression_label': label,
            'column_group_index': 0,
        })
        return self.env['account.move.line'].search(action['domain'])

    def test_group_of_taxes_report_each_jurisdiction(self):
        """ Test that a base line tagged with a group of taxes is reported. """
        self._create_invoice_and_options(self.tax_group)
        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           100.0,  0.0,    0.0,        100.0,  '',         9.5),
                ('California',      100.0,  0.0,    0.0,        100.0,  '',         9.5),
                ('CA State',        100.0,  0.0,    0.0,        100.0,  '6.0000%',  6.0),
                ('San Mateo County', 100.0, 0.0,    0.0,        100.0,  '2.2500%',  2.25),
                ('CA Special',      100.0,  0.0,    0.0,        100.0,  '1.2500%',  1.25),
                ('Total California', 100.0, 0.0,    0.0,        100.0,  '',         9.5),
                ('Total Sales',     100.0,  0.0,    0.0,        100.0,  '',         9.5),
            ],
            self.options,
        )

    def test_group_of_taxes_audit_base_columns(self):
        """ Tests that auditing shows the base lines with a group of taxes applied. """
        self._create_invoice_and_options(self.tax_group)
        base_line = self._base_lines(self.tax_group)

        for tax in self.tax_state | self.tax_county | self.tax_special:
            for label in ('net', 'taxable'):
                with self.subTest(tax=tax.name, label=label):
                    self.assertEqual(self._audit_cell(tax, label), base_line)

    def test_reduced_rate_reported_as_taxable(self):
        """ Test that a reduced rate tax does not get a report line of its own.
        It must be aggregated into its parent tax row. """
        self._create_invoice_and_options(self.tax_state, self.tax_exempt, self.tax_non_taxable, self.tax_reduced)
        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           400.0,  100.0,  100.0,      200.0,  '',         10.0),
                ('California',      400.0,  100.0,  100.0,      200.0,  '',         10.0),
                ('CA State',        400.0,  100.0,  100.0,      200.0,  '6.0000%',  10.0),
                ('Total California', 400.0, 100.0,  100.0,      200.0,  '',         10.0),
                ('Total Sales',     400.0,  100.0,  100.0,      200.0,  '',         10.0),
            ],
            self.options,
        )

    def test_totals_count_each_base_line_once(self):
        """ Test that the header column totals are a sum of the base lines to avoid double counting. """
        self._create_invoice_and_options(self.tax_group, self.tax_state, self.tax_exempt)
        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           300.0,  100.0,  0.0,        200.0,  '',         15.5),
                ('California',      300.0,  100.0,  0.0,        200.0,  '',         15.5),
                ('CA State',        300.0,  100.0,  0.0,        200.0,  '6.0000%',  12.0),
                ('San Mateo County', 100.0, 0.0,    0.0,        100.0,  '2.2500%',  2.25),
                ('CA Special',      100.0,  0.0,    0.0,        100.0,  '1.2500%',  1.25),
                ('Total California', 300.0, 100.0,  0.0,        200.0,  '',         15.5),
                ('Total Sales',     300.0,  100.0,  0.0,        200.0,  '',         15.5),
            ],
            self.options,
        )

    def test_taxes_without_jurisdiction_type_reported_as_undefined(self):
        """ Test that the taxes without jurisdiction type are grouped in an 'Undefined' section after the states. """
        tax_undefined = self.env['account.tax'].create({
            'name': "Undefined Tax",
            'amount': 5.0,
            'type_tax_use': 'sale',
        })
        self._create_invoice_and_options(self.tax_state, tax_undefined)
        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           200.0,  0.0,    0.0,        200.0,  '',         11.0),
                ('California',      100.0,  0.0,    0.0,        100.0,  '',         6.0),
                ('CA State',        100.0,  0.0,    0.0,        100.0,  '6.0000%',  6.0),
                ('Total California', 100.0, 0.0,    0.0,        100.0,  '',         6.0),
                ('Undefined',       100.0,  0.0,    0.0,        100.0,  '',         5.0),
                ('Undefined Tax',   100.0,  0.0,    0.0,        100.0,  '5.0000%',  5.0),
                ('Total Undefined', 100.0,  0.0,    0.0,        100.0,  '',         5.0),
                ('Total Sales',     200.0,  0.0,    0.0,        200.0,  '',         11.0),
            ],
            self.options,
        )

    def test_zero_rate_tax_without_jurisdiction_type_keeps_its_base(self):
        """ Test that a 0% tax without jurisdiction type still reports the base it levies. """
        tax_zero = self.env['account.tax'].create({
            'name': "Zero Tax",
            'amount': 0.0,
            'type_tax_use': 'sale',
        })
        self._create_invoice_and_options(tax_zero)
        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           100.0,  0.0,    0.0,        100.0,  '',         0.0),
                ('Undefined',       100.0,  0.0,    0.0,        100.0,  '',         0.0),
                ('Zero Tax',        100.0,  0.0,    0.0,        100.0,  '0.0000%',  0.0),
                ('Total Undefined', 100.0,  0.0,    0.0,        100.0,  '',         0.0),
                ('Total Sales',     100.0,  0.0,    0.0,        100.0,  '',         0.0),
            ],
            self.options,
        )

    def test_cash_basis_tax_reported_once_paid(self):
        """ Test that a cash basis tax is left out of the report until the payment makes it exigible. """
        self.env.company.tax_exigibility = True
        tax_cash_basis = self._create_jurisdiction_tax(
            "CA Cash Basis", 6.0,
            tax_exigibility='on_payment',
            cash_basis_transition_account_id=self.cash_basis_account.id,
        )
        self._create_invoice_and_options(tax_cash_basis)
        self.assertFalse(self.report._get_lines(self.options), "the tax is not exigible before the payment")

        self.env['account.payment.register'].with_context(
            active_ids=self.invoice.ids, active_model='account.move',
        ).create({'payment_date': self.invoice.invoice_date})._create_payments()

        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           100.0,  0.0,    0.0,        100.0,  '',         6.0),
                ('California',      100.0,  0.0,    0.0,        100.0,  '',         6.0),
                ('CA Cash Basis',   100.0,  0.0,    0.0,        100.0,  '6.0000%',  6.0),
                ('Total California', 100.0, 0.0,    0.0,        100.0,  '',         6.0),
                ('Total Sales',     100.0,  0.0,    0.0,        100.0,  '',         6.0),
            ],
            self.options,
        )

    def test_cash_basis_tax_mixed_with_accrual_tax(self):
        """ Test that a base line levied by both an accrual and a cash basis tax is only
        reported for the accrual tax until the payment makes the other one exigible. """
        self.env.company.tax_exigibility = True
        tax_cash_basis = self._create_jurisdiction_tax(
            "SMC Cash Basis", 2.25, 'county',
            l10n_us_county_id=self.san_mateo.id,
            tax_exigibility='on_payment',
            cash_basis_transition_account_id=self.cash_basis_account.id,
        )
        self._create_invoice_and_options(self.tax_state | tax_cash_basis)
        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           100.0,  0.0,    0.0,        100.0,  '',         6.0),
                ('California',      100.0,  0.0,    0.0,        100.0,  '',         6.0),
                ('CA State',        100.0,  0.0,    0.0,        100.0,  '6.0000%',  6.0),
                ('Total California', 100.0, 0.0,    0.0,        100.0,  '',         6.0),
                ('Total Sales',     100.0,  0.0,    0.0,        100.0,  '',         6.0),
            ],
            self.options,
        )

        self.env['account.payment.register'].with_context(
            active_ids=self.invoice.ids, active_model='account.move',
        ).create({'payment_date': self.invoice.invoice_date})._create_payments()

        # The base is reported per jurisdiction, so the header totals it in both periods it falls due.
        self.assertLinesValues(
            self.report._get_lines(self.options),
            #   Name                Gross   Exempt  Non-Taxable Taxable Rate        Tax
            [   0,                  1,      2,      3,          4,      5,          6],
            [
                ('Sales',           200.0,  0.0,    0.0,        200.0,  '',         8.25),
                ('California',      200.0,  0.0,    0.0,        200.0,  '',         8.25),
                ('CA State',        100.0,  0.0,    0.0,        100.0,  '6.0000%',  6.0),
                ('SMC Cash Basis',  100.0,  0.0,    0.0,        100.0,  '2.2500%',  2.25),
                ('Total California', 200.0, 0.0,    0.0,        200.0,  '',         8.25),
                ('Total Sales',     200.0,  0.0,    0.0,        200.0,  '',         8.25),
            ],
            self.options,
        )

    def test_reduced_rate_audit_columns(self):
        """ Test that each cell audits the move lines it aggregates, including the the reduced rate taxes. """
        self._create_invoice_and_options(self.tax_state, self.tax_exempt, self.tax_non_taxable, self.tax_reduced)
        expected_per_label = {
            'net': self._base_lines(self.tax_state | self.tax_exempt | self.tax_non_taxable | self.tax_reduced),
            'exempt': self._base_lines(self.tax_exempt),
            'non_taxable': self._base_lines(self.tax_non_taxable),
            'taxable': self._base_lines(self.tax_state | self.tax_reduced),
            'tax': self.invoice.line_ids.filtered(lambda line: line.tax_line_id in self.tax_state | self.tax_reduced),
        }

        for label, expected_lines in expected_per_label.items():
            with self.subTest(label=label):
                self.assertEqual(self._audit_cell(self.tax_state, label), expected_lines)
