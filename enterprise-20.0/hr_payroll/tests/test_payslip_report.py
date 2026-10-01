from odoo.fields import Command, Date
from odoo.tests.common import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('post_install', '-at_install')
class TestPayslipReport(TestPayslipContractBase):

    def test_hours_format_in_pdf(self):
        """
        Test that worked hours are correctly formatted in the payslip PDF report.
        Verify that 7.2 hours is rendered as 07:12 in the report.
        """

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.richard_emp.id,
            'version_id': self.richard_contract.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': Date.to_date('2026-02-01'),
            'date_to': Date.to_date('2026-02-28'),
            'company_id': self.company_us.id,
            'worked_days_line_ids': [Command.create({
                'name': 'Attendance',
                'number_of_hours': 7.2,
                'work_entry_type_id': self.work_entry_type.id,
                'version_id': self.richard_contract.id,
                'amount': 100.0,
            })]
        })

        report = self.env.ref('hr_payroll.action_report_payslip')
        content, _ = report.sudo().with_context(lang='en_US')._render_qweb_pdf(
            report.report_name,
            res_ids=payslip.ids
        )
        html_text = str(content.decode('utf-8'))

        self.assertIn('>07:12<', html_text, "The report should format 7.2 as 07:12")
        self.assertNotIn('>7.2<', html_text, "The report should not show the raw decimal 7.2")
