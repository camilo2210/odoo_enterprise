from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUSAccountReport(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.report = cls.env.ref('l10n_us_reports.profit_and_loss')
        cls.options = cls._generate_options(cls.report, '2026-01-01', '2026-12-31')
        cls.lines_to_bold = [
            cls._get_basic_line_dict_id_from_report_line_ref(xmlid)
            for xmlid in (
                'l10n_us_reports.pl_gross_profit',
                'l10n_us_reports.pl_net_operating_income',
                'l10n_us_reports.pl_net_other_income',
            )
        ]

    def _get_matching_lines(self, line_ids):
        """ Return report lines matching the given IDs."""
        report_lines = self.report._get_lines(self.options)
        return [line for line in report_lines if line.id in line_ids]

    def test_us_profit_and_loss_summary_lines_are_bold(self):
        """
        Test that key summary lines in the US P&L report are rendered in bold.
        """
        bold_lines = self._get_matching_lines(self.lines_to_bold)
        self.assertEqual(len(bold_lines), len(self.lines_to_bold))
        for line in bold_lines:
            self.assertIn('fw-bold', line.css_class)

    def test_us_profit_and_loss_with_deleted_summary_line(self):
        """
        Test that the P&L report ignores deleted summary lines without raising error.
        """
        self.env.ref('l10n_us_reports.pl_gross_profit').unlink()
        bold_lines = self._get_matching_lines(self.lines_to_bold)
        self.assertEqual(len(bold_lines), len(self.lines_to_bold) - 1)
