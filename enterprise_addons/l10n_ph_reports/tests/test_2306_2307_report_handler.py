# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.tests import tagged
from odoo.tools import html2plaintext
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.l10n_ph.tests.common import TestPhCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPH23062307ReportHandlers(TestAccountReportsCommon, TestPhCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('ph')
    def setUpClass(cls):
        super().setUpClass()

        ChartTemplate = cls.env["account.chart.template"].with_company(cls.company_data["company"])

        tax_2307_5 = ChartTemplate.ref('l10n_ph_tax_purchase_5_wi100')
        tax_2307_10 = ChartTemplate.ref('l10n_ph_tax_purchase_10_wi011')

        tax_2306_25 = ChartTemplate.ref('l10n_ph_tax_purchase_25_wc830')
        tax_2306_12 = ChartTemplate.ref('l10n_ph_tax_purchase_12_fwvat_ds')

        # The purchase withholding taxes are withheld at payment time, so they need a sequence
        # to number the withholding entries created when registering the payments below.
        withholding_sequence = cls.env['ir.sequence'].create({
            'implementation': 'no_gap',
            'name': 'Withholding Sequence',
            'padding': 4,
            'number_increment': 1,
        })
        (tax_2307_5 | tax_2307_10 | tax_2306_25).withholding_sequence_id = withholding_sequence

        invoice_data = [
            # 2307
            ('in_invoice', cls.partner_a, '2025-10-16', [(1000, tax_2307_5)]),
            ('in_invoice', cls.partner_a, '2025-11-16', [(2000, tax_2307_10)]),
            ('in_invoice', cls.partner_a, '2025-11-19', [(500, tax_2307_10)]),
            ('in_invoice', cls.partner_b, '2025-11-15', [(5000, tax_2307_10)]),

            # 2306
            ('in_invoice', cls.partner_a, '2025-10-15', [(500, tax_2306_12)]),
            ('in_invoice', cls.partner_b, '2025-11-16', [(1000, tax_2306_12)]),
            ('in_invoice', cls.partner_b, '2025-11-16', [(5000, tax_2306_25)]),

             # Ignored in the report
            ('in_invoice', cls.partner_a, '2025-10-16', [(1000, False)]),
        ]
        invoice_vals = []
        for move_type, partner, invoice_date, lines in invoice_data:
            invoice_vals.append({
                'move_type': move_type,
                'invoice_date': invoice_date,
                'partner_id': partner.id,
                'invoice_line_ids': [
                    Command.create({
                        'name': 'Test line',
                        'quantity': 1.0,
                        'price_unit': amount,
                        'tax_ids': tax,
                    }) for amount, tax in lines
                ]
            })
        invoices = cls.env['account.move'].create(invoice_vals)
        invoices.action_post()

        # Withholding is applied at payment time, so register a payment per invoice to create
        # the withholding entries the 2306/2307 reports read from.
        for invoice in invoices:
            cls.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=invoice.ids
            ).create({'payment_date': invoice.invoice_date})._create_payments()

        cls.env.company.totals_below_sections = False

    def test_2306_report_generation_and_content(self):
        """ It verifies that the correct partner is found and the calculations are correct for 2306 report. """
        report = self.env.ref('l10n_ph_reports.2306_report')
        options = self._generate_options(report, '2025-10-01', '2025-11-30')

        lines = report._get_lines(options)
        self.assertEqual(len(lines), 3)

        # Test Level 1: Partner and Grand Total Lines
        self.assertLinesValues(
            lines,
            #    Name,                         Amount of Income Payments, Tax Withheld
            [    0,                            1,                              2],
            [
                [                          '', 6500.0,                    1430.0],
                [self.partner_a.complete_name, 500.0,                       60.0],   # Partner A line
                [self.partner_b.complete_name, 6000.0,                    1370.0],   # Partner B line
            ],
            options
        )

        # Test Level 1 (ATC) and Level 2 (Move) Lines for Partner A
        partner_a_options = self._generate_options(report, '2025-10-01', '2025-11-30',
            default_options={
                'partner_ids': [self.partner_a],
                'unfold_all': True,
            }
        )
        partner_a_lines = report._get_lines(partner_a_options)
        partner_a_atc_move_lines = [line for line in partner_a_lines if line.groupby == 'move_id' and line.unfoldable or not line.groupby]
        self.assertLinesValues(
            partner_a_atc_move_lines,
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [
                [500.0,                     60.0],  # Level 1 - 12% Tax: Total from 1 invoice (500)
                [500.0,                     60.0],  # Level 2 - Move 1 (12%): Invoice for 500
            ],
            partner_a_options
        )

        # Test Level 1 (ATC) and Level 2 (Move) Lines for Partner B
        partner_b_options = self._generate_options(report, '2025-10-01', '2025-11-30',
            default_options={
                'partner_ids': [self.partner_b],
                'unfold_all': True,
            }
        )
        partner_b_lines = report._get_lines(partner_b_options)
        partner_b_atc_move_lines = [line for line in partner_b_lines if line.groupby == 'move_id' and line.unfoldable or not line.groupby]
        self.assertLinesValues(
            partner_b_atc_move_lines,
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [
                [5000.0,                      1250.0],  # Level 1 - 25% Tax: Total from 1 invoice (5000)
                [5000.0,                      1250.0],  # Level 2 - Move 1 (25%): Invoice for 5000
                [1000.0,                       120.0],  # Level 1 - 12% Tax: Total from 1 invoice (1000)
                [1000.0,                       120.0],  # Level 2 - Move 2 (12%): Invoice for 1000
            ],
            partner_b_options
        )

    def test_2307_report_generation_and_content(self):
        """ It verifies that the correct partner is found and the calculations are correct for 2307 report. """
        report = self.env.ref('l10n_ph_reports.2307_report')
        options = self._generate_options(report, '2025-10-01', '2025-11-30')

        lines = report._get_lines(options)

        self.assertEqual(len(lines), 3)

        # Test Level 1: Partner and Grand Total Lines
        self.assertLinesValues(
            lines,
            #    Name,                         Amount of Income Payments, Tax Withheld
            [    0,                            1,                         2],
            [
                [                          '', 8500.0,                     800.0],
                [self.partner_a.complete_name, 3500.0,                     300.0],  # Partner A line
                [self.partner_b.complete_name, 5000.0,                     500.0],  # Partner B line
            ],
            options
        )

        # Test Level 1 (ATC) and Level 2 (Move) Lines for Partner A
        partner_a_options = self._generate_options(report, '2025-10-01', '2025-11-30',
            default_options={
                'partner_ids': [self.partner_a],
                'unfold_all': True,
            }
        )
        partner_a_lines = report._get_lines(partner_a_options)
        partner_a_atc_move_lines = [line for line in partner_a_lines if line.groupby == 'move_id' and line.unfoldable or not line.groupby]
        self.assertLinesValues(
            partner_a_atc_move_lines,
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [
                [2500.0,                    250.0],  # Level 1 - 10% Tax: Total from 2 invoices (2000 + 500)
                [ 500.0,                     50.0],  # Level 2 - Move 1 (10%): Invoice for 500
                [2000.0,                    200.0],  # Level 2 - Move 2 (10%): Invoice for 2000
                [1000.0,                     50.0],  # Level 1 - 5% Tax: Total from 1 invoice (1000)
                [1000.0,                     50.0],  # Level 2 - Move 1 (5%): Invoice for 1000
            ],
            partner_a_options
        )

        # Test Level 1 (ATC) and Level 2 (Move) Lines for Partner B
        partner_b_options = self._generate_options(report, '2025-10-01', '2025-11-30',
            default_options={
                'partner_ids': [self.partner_b],
                'unfold_all': True,
            }
        )
        partner_b_lines = report._get_lines(partner_b_options)
        partner_b_atc_move_lines = [line for line in partner_b_lines if line.groupby == 'move_id' and line.unfoldable or not line.groupby]
        self.assertLinesValues(
            partner_b_atc_move_lines,
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [
                [5000.0,                    500.0],  # Level 1 - 10% Tax: Total from 1 invoice (5000)
                [5000.0,                    500.0],  # Level 2 - Move 1 (10%): Invoice for 5000
            ],
            partner_b_options
        )

    def test_2307_report_month_wise_totals(self):
        """ Test grand totals are calculated correctly for months """
        report = self.env.ref('l10n_ph_reports.2307_report')

        options = self._generate_options(report, '2025-10-01', '2025-12-20',
            default_options={
                'unfold_all': True,
                'partner_ids': [self.partner_a],
            }
        )

        lines = report.with_context(l10n_ph_is_certificate_generation=True)._get_lines(options)
        total_line = next((l for l in lines if l.unfoldable and l.groupby == "tax_line_id,move_id"), None)

        self.assertEqual(total_line.custom['first_month_base_total'], 1000.0)
        self.assertEqual(total_line.custom['second_month_base_total'], 2500.0)
        self.assertEqual(total_line.custom['third_month_base_total'], 0.0)

    def test_2306_report_resolves_group_tax_children(self):
        """ It verifies that the 2306 report groups and unfolds a group tax's reverse-charge child. """
        ChartTemplate = self.env["account.chart.template"].with_company(self.company_data["company"])
        rc_tax = ChartTemplate.ref('l10n_ph_tax_purchase_12_fwvat_ds_rc')
        self.assertEqual(rc_tax.type_tax_use, 'purchase')
        self.assertTrue(rc_tax.is_withholding_tax)

        report = self.env.ref('l10n_ph_reports.2306_report')
        options = self._generate_options(report, '2025-10-01', '2025-11-30',
            default_options={
                'partner_ids': [self.partner_a],
                'unfold_all': True,
            }
        )
        lines = report._get_lines(options)
        atc_move_lines = [line for line in lines if line.groupby == 'move_id' and line.unfoldable or not line.groupby]

        # The reverse-charge child is grouped under its own ATC/description, and unfolding down
        # to its move only works because the report resolves the child of the group tax.
        self.assertEqual(atc_move_lines[0].name, f"{rc_tax.l10n_ph_atc} - {html2plaintext(rc_tax.description)}")
        self.assertLinesValues(
            atc_move_lines,
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [
                [500.0,                     60.0],  # Level 1 - ATC (12% FWVAT DS reverse charge): Total from 1 invoice (500)
                [500.0,                     60.0],  # Level 2 - Move 1: Invoice for 500
            ],
            options,
        )

    def test_2307_certificate_atc_lines_present_when_folded(self):
        """ The certificate PDF is rendered with the tree folded (no unfold_all). The ATC
        (tax_line_id) lines and their month-wise base amounts must still reach the template,
        i.e. survive _filter_out_folded_children. """
        report = self.env.ref('l10n_ph_reports.2307_report')

        # Mirror the production certificate path: print options, no unfold_all.
        options = self._generate_options(report, '2025-10-01', '2025-12-20',
            default_options={'partner_ids': [self.partner_a]},
        )
        options = report.get_options(previous_options={**options, 'export_mode': 'print'})

        lines = report.with_context(l10n_ph_is_certificate_generation=True)._get_lines(options)
        lines = report._filter_out_folded_children(lines)

        # Amount of Income Payments and Tax Withheld for each ATC line.
        self.assertLinesValues(
            lines,
            #    Name,                                 Amount of Income Payments, Tax Withheld
            [    0,                                    1,                         2],
            [
                ['',                                   3500.00,                   300.00],
                ['John Doe Smith',                     3500.00,                   300.00],
                ['WI011 - Prof Fees',                  2500.00,                   250.00],  # 10% Tax: 2000 + 500
                ['WI100 - Gross rental of property',   1000.00,                   50.00],   # 5% Tax: 1000
            ],
            options
        )

    def test_2306_income_payment_combines_bill_and_payment_withholding(self):
        """ It verifies that the 2306 report adds the income payments of a partner whose
        withholding is recorded both on the bill (12% FWVAT) and at payment (25% WC830). """
        report = self.env.ref('l10n_ph_reports.2306_report')
        options = self._generate_options(report, '2025-10-01', '2025-11-30',
            default_options={
                'partner_ids': [self.partner_b],
                'unfold_all': True,
            }
        )
        lines = report._get_lines(options)

        # Partner total: both income payments made to partner B are summed. The 5000 paid with
        # the 25% tax and the 1000 paid with the 12% tax add up to a 6000 income payment.
        partner_b_lines = [line for line in lines if line.name == self.partner_b.complete_name]
        self.assertLinesValues(
            partner_b_lines,
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [
                [6000.0,                     1370.0],  # 5000 (25%) + 1000 (12%)
            ],
            options
        )

        # Breakdown: the income payment and tax of each ATC (25% and 12%) and its underlying invoice.
        atc_move_lines = [line for line in lines if line.groupby == 'move_id' and line.unfoldable or not line.groupby]
        self.assertLinesValues(
            atc_move_lines,
            #    Amount of Income Payments, Tax Withheld
            [    1,                         2],
            [
                [5000.0,                     1250.0],  # 25% Tax (withheld at payment): invoice for 5000
                [5000.0,                     1250.0],
                [1000.0,                      120.0],  # 12% Tax (recorded on the bill): invoice for 1000
                [1000.0,                      120.0],
            ],
            options
        )
