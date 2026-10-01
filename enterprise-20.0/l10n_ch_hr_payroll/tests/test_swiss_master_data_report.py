# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import tagged, TransactionCase


@tagged('post_install_l10n', 'post_install', '-at_install', 'swissdec_payroll')
class TestSwissMasterDataReport(TransactionCase):

    def test_wage_types_report_compilation(self):
        """This test verifies that the Swiss Wage Types report is generated successfully."""
        report = self.env.ref('l10n_ch_hr_payroll.action_l10n_ch_company_wage_type_report')
        salary_rule = self.env['hr.salary.rule'].search([('l10n_ch_code', '!=', False)], limit=1)
        data = {
            'doc': {
                'company': self.env.company,
                'salary_rules': salary_rule
            },
            'year': 2026,
            'month': '1',
        }

        html_content, _ = self.env["ir.actions.report"]._render_qweb_html(report, [1], data=data)
        self.assertTrue(html_content, "The report content should not be empty")
        self.assertIn(self.env.company.name, str(html_content), "The company name should be in the report")
        self.assertIn(salary_rule.name, str(html_content), "The salary rule name should be in the report")
