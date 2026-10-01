from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestProfitAndLoss(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('fr_comp')
    def setUpClass(cls):
        super().setUpClass()

    def test_profit_and_loss_pcg_lines(self):
        report = self.env.ref('l10n_fr_reports.account_financial_report_l10n_fr_cdr')
        options = self._generate_options(report, '2025-01-01', '2025-12-31')

        line_codes = {line.code for line in report._get_lines(options)}

        self.assertTrue({
            'i_revenue',
            'i_disposal',
            'ii_disposal',
            'v_6',
            'v_7',
            'vi_5',
            'vi_6',
            'VII',
            'VIII',
        } <= line_codes)

    def test_profit_and_loss_comparison_columns(self):
        report = self.env.ref('l10n_fr_reports.account_financial_report_l10n_fr_cdr')
        options = self._generate_options(report, '2025-01-01', '2025-12-31', default_options={
            'comparison': {
                'filter': 'same_last_year',
                'number_period': 1,
            },
        })

        self.assertNotIn('column_percent_comparison', options)

    def test_profit_and_loss_pcg_account_mapping(self):
        expected_formulas = {
            'l10n_fr_reports.account_financial_report_line_fr_cdrp2_balance': '-701 - 706 - 7092 - 704 - 702 - 7098 - 705 - 7094 - 7096 - 7095 - 7091 - 703 - 708',
            'l10n_fr_reports.account_financial_report_line_fr_cdrp_disposal_balance': '-757',
            'l10n_fr_reports.account_financial_report_line_fr_cdrc8_balance': '631 + 633 + 635 + 637 + 638',
            'l10n_fr_reports.account_financial_report_line_fr_cdrc10_balance': '645 + 646 + 647 + 6492',
            'l10n_fr_reports.account_financial_report_line_fr_cdrc_disposal_balance': '657',
            'l10n_fr_reports.account_financial_report_line_fr_cdrc18_balance': '661 + 664 + 665 + 668',
        }
        for expression_xmlid, formula in expected_formulas.items():
            self.assertEqual(self.env.ref(expression_xmlid).formula, formula)

    def test_profit_and_loss_legacy_line_xmlids(self):
        expected_codes = {
            'l10n_fr_reports.account_financial_report_line_fr_cdrp3': 'i_3',
            'l10n_fr_reports.account_financial_report_line_fr_cdrp7': 'i_7',
            'l10n_fr_reports.account_financial_report_line_fr_cdrc16': 'ii_13',
        }
        for line_xmlid, code in expected_codes.items():
            self.assertEqual(self.env.ref(line_xmlid).code, code)
