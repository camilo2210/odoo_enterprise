from odoo import fields
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestIntercoComparisonReport(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref('account_reports.interco_comparison_report')

    def test_tax_lines_hidden_by_default(self):
        options = self._generate_options(self.report, fields.Date.from_string('2024-01-01'), fields.Date.from_string('2024-12-31'))

        self.assertTrue(options['hide_tax_lines'])
        self.assertIn(('tax_line_id', '=', False), options['forced_domain'])

    def test_tax_lines_shown_when_the_filter_is_unset(self):
        options = self._generate_options(
            self.report,
            fields.Date.from_string('2024-01-01'),
            fields.Date.from_string('2024-12-31'),
            default_options={'hide_tax_lines': False},
        )

        self.assertFalse(options['hide_tax_lines'])
        self.assertNotIn(('tax_line_id', '=', False), options['forced_domain'])
