from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.fields import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestXBRLExports(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.update({
            'street': 'Rue du Paradis 200',
            'zip': '1000',
            'vat': 'BE0897223670',
            'l10n_be_company_type_id': cls.env['l10n_be.company.type'].search([], limit=1).id,
        })

    def _generate_file(self, report, options):
        """ Helper to generate the XBRL file with mocked data for the extra data method. If other
        modules override this method, we don't want to test their behavior here, just the XBRL export. """
        with patch.object(self.env.registry[report.custom_handler_model_name], '_get_extra_file_data', return_value={}):
            return self.env[report.custom_handler_model_name].generate_xbrl_file(options)

    def _get_be_report(self, chart_template):
        return next(
            variant for variant in self.env.ref('account_reports.annual_statements').variant_report_ids
            if variant.chart_template == chart_template
        )

    def _activate_report_pair(self, be_report, balance_sheet_xmlid, profit_and_loss_xmlid):
        be_report.section_report_ids.active = False
        self.env.ref(balance_sheet_xmlid).active = True
        self.env.ref(profit_and_loss_xmlid).active = True

    def _generate_be_xbrl_file(self, chart_template, balance_sheet_xmlid, profit_and_loss_xmlid, date_to):
        base_report = self.env.ref('account_reports.annual_statements')
        be_report = self._get_be_report(chart_template)
        self._activate_report_pair(be_report, balance_sheet_xmlid, profit_and_loss_xmlid)
        fiscal_dates = self.company.compute_fiscalyear_dates(fields.Date.to_date(date_to))
        options = self._generate_options(be_report, fiscal_dates['date_from'], fiscal_dates['date_to'])
        options['report_id'] = be_report.id
        options['last_deed_date'] = '2024-06-30'
        return self._generate_file(base_report, options)

    def _get_or_create_account(self, code, account_type):
        account = self.env['account.account'].search([
            *self.env['account.account']._check_company_domain(self.company.id),
            ('code', '=', code),
        ], limit=1)
        return account or self.env['account.account'].create({
            'name': code,
            'code': code,
            'account_type': account_type,
        })

    @freeze_time('2025-06-30')
    def test_all_context_used(self):
        """ Test that all context tags are used in the XBRL export. """

        report_versions = [
            ('be_comp', [('comp_acon', 'comp_a'), ('comp_fcon', 'comp_f'), ('comp_acap', 'comp_a'), ('comp_fcap', 'comp_f')]),
            ('be_asso', [('asso_a', 'asso_a'), ('asso_f', 'asso_f')]),
        ]
        for chart_template, versions in report_versions:
            for version in versions:
                xbrl_file = self._generate_be_xbrl_file(
                    chart_template=chart_template,
                    balance_sheet_xmlid=f'l10n_be_reports.account_financial_report_bs_{version[0]}',
                    profit_and_loss_xmlid=f'l10n_be_reports.account_financial_report_pl_{version[1]}',
                    date_to=fields.Date.today(),
                )

                self.assertTrue(xbrl_file)
                self.assertEqual(xbrl_file['file_type'], 'xml')

                file_content = self.get_xml_tree_from_string(xbrl_file['file_content'])

                # Check that the root element is 'xbrl'
                self.assertTrue(file_content.tag.endswith('xbrl'))

                context = file_content.findall('.//{*}context')
                context_refs = file_content.findall('.//*[@contextRef]')

                context_ids = {c.attrib.get('id') for c in context}
                context_ref_values = {c.attrib.get('contextRef') for c in context_refs}
                missing_context_ids = context_ref_values - context_ids

                self.assertEqual(len(missing_context_ids), 0, f"Each contextRef should have a corresponding context element in XBRL template: {version}. Missing {missing_context_ids} context ids.")

                # Check that each context id is unique
                self.assertEqual(len(context), len(context_ids), f"Each context id should be unique in XBRL template: {version}")
                self.assertEqual(len(context_refs), len(context_ref_values), f"Each contextRef should be unique in XBRL template: {version}")

                # Check that each contextRef matches an existing context id
                for value in context_refs:
                    self.assertIn(value.attrib.get('contextRef'), context_ids, f"contextRef should match an existing context id in XBRL template: {version}")

                # Check that required context tags are present
                expected_context_vars = {
                    'registration_number', 'date', 'start_period', 'end_period',
                    'company_name', 'company_type', 'company_street', 'company_house_number',
                    'company_postal_code', 'company_country', 'company_region', 'last_deed_date',
                }
                for var in expected_context_vars:
                    self.assertIn(var, context_ids, f"Context variable '{var}' is missing in XBRL template: {version}")

    def test_wrong_report_selection(self):
        """ Test that an error is raised when the selected reports do not match the XBRL export requirements. """

        base_report = self.env.ref('account_reports.annual_statements')
        be_report = self._get_be_report('be_comp')

        # Try to generate XBRL from non-Belgian report
        options = self._generate_options(base_report, False, fields.Date.today())
        with self.assertRaisesRegex(UserError, r"XBRL export is only applicable for Belgium reports. Please change to Belgium annual statement report."):
            self._generate_file(base_report, options)

        # Using Belgian report, select only one report instead of a pair of balance sheet and profit & loss
        be_report.section_report_ids.active = False
        self.env.ref('l10n_be_reports.account_financial_report_bs_comp_acon').active = True

        options = self._generate_options(be_report, False, fields.Date.today())
        options['report_id'] = be_report.id

        with self.assertRaisesRegex(UserError, r"Please add a single balance sheet and a single profit and loss report that have a matching \(Abbr or Full\) format for the XBRL export."):
            self._generate_file(base_report, options)

        # Now select a pair of reports with initial wrong selection
        self.env.ref('l10n_be_reports.account_financial_report_bs_comp_acap').active = True
        self.env.ref('l10n_be_reports.account_financial_report_pl_comp_a').active = True

        with self.assertRaisesRegex(UserError, r"Please add a single balance sheet and a single profit and loss report that have a matching \(Abbr or Full\) format for the XBRL export."):
            self._generate_file(base_report, options)

        # Now with a valid pair of reports
        self._activate_report_pair(
            be_report,
            'l10n_be_reports.account_financial_report_bs_comp_fcon',
            'l10n_be_reports.account_financial_report_pl_comp_f',
        )

        xbrl_file = self._generate_file(base_report, options)
        self.assertTrue(xbrl_file)
        self.assertEqual(xbrl_file['file_type'], 'xml')

    def test_alphanumeric_zip_code(self):
        """
        Test that the Belgian region is correctly computed for a valid numeric ZIP code
        and that it is safely ignored for non-numeric ZIP codes.
        """
        self.company.l10n_be_region_id = False

        self.company.zip = 'R93R2R3'
        self.assertFalse(self.company.l10n_be_region_id)

        self.company.zip = '1000'
        self.assertTrue(self.company.l10n_be_region_id)

    def test_all_disclosures_present_in_xbrl(self):
        counterpart_account = self.company_data['default_journal_bank'].default_account_id
        move_specs = [
            ('280000', 'asset_non_current', 100.0, 0.0, {}),
            ('280800', 'asset_non_current', 20.0, 0.0, {}),
            ('280900', 'asset_non_current', 0.0, 5.0, {}),
            ('280100', 'asset_non_current', 0.0, 7.0, {}),
            ('220000', 'asset_fixed', 200.0, 0.0, {}),
            ('220008', 'asset_fixed', 30.0, 0.0, {}),
            ('220009', 'asset_fixed', 0.0, 40.0, {}),
            ('174', 'liability_non_current', 0.0, 50.0, {'date_maturity': '2027-06-15'}),
            ('174', 'liability_non_current', 0.0, 60.0, {'date_maturity': '2032-06-15'}),
            ('630000', 'expense_depreciation', 11.0, 0.0, {}),
            ('630100', 'expense_depreciation', 12.0, 0.0, {}),
            ('630800', 'expense_other', 13.0, 0.0, {}),
            ('630200', 'expense_depreciation', 14.0, 0.0, {}),
            ('630900', 'expense_other', 15.0, 0.0, {}),
        ]
        for code, account_type, debit, credit, extra_vals in move_specs:
            account = self._get_or_create_account(code, account_type)
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'date': '2025-06-15',
                'journal_id': self.company_data['default_journal_misc'].id,
                'line_ids': [
                    Command.create({
                        'account_id': account.id,
                        'debit': debit,
                        'credit': credit,
                        **extra_vals,
                    }),
                    Command.create({
                        'account_id': counterpart_account.id,
                        'debit': credit,
                        'credit': debit,
                    }),
                ],
            })
            move.action_post()

        xbrl_file = self._generate_be_xbrl_file(
            chart_template='be_comp',
            balance_sheet_xmlid='l10n_be_reports.account_financial_report_bs_comp_acon',
            profit_and_loss_xmlid='l10n_be_reports.account_financial_report_pl_comp_a',
            date_to='2025-12-31',
        )
        file_content = self.get_xml_tree_from_string(xbrl_file['file_content'])

        expected_disclosures = {
            'exp_disclosure_financial_acquisition': 100.0,
            'exp_disclosure_financial_capital_gains': 20.0,
            'exp_disclosure_financial_amount_written_down': 5.0,
            'exp_disclosure_financial_uncalled_amount': 7.0,
            'exp_disclosure_tangible_acquisition': 200.0,
            'exp_disclosure_tangible_revaluation_surplus': 30.0,
            'exp_disclosure_tangible_amount_written_down': 40.0,
            'exp_disclosure_payable_more_than_one_less_than_five': 50.0,
            'exp_disclosure_payable_more_than_five': 60.0,
            'exp_disclosure_depreciation_on_formation_expense': 11.0,
            'exp_disclosure_depreciation_on_intangible_assets': 54.0,
        }
        for context_ref, expected_value in expected_disclosures.items():
            disclosure_values = file_content.findall(f'.//*[@contextRef="{context_ref}"]')
            self.assertTrue(disclosure_values, f"Expected disclosure {context_ref} to be present in the XBRL export.")
            self.assertEqual(float(disclosure_values[0].text), expected_value)
