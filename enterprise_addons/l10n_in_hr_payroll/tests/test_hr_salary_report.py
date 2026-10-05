from datetime import date

from odoo.addons.l10n_in_hr_payroll.tests.common import TestPayrollCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrSalaryReport(TestPayrollCommon):

    def test_l10n_in_yearly_salary_report_creation(self):
        payslips = self.env['hr.payslip'].create([{
                'name': 'Jethalal Payslip',
                'employee_id': self.jethalal_emp.id,
                'version_id': self.contract_jethalal.id,
                'date_from': date(2023, 1, 1),
                'date_to': date(2023, 1, 31),
            }, {
                'name': 'Rahul Payslip',
                'employee_id': self.rahul_emp.id,
                'version_id': self.contract_rahul.id,
                'date_from': date(2023, 1, 1),
                'date_to': date(2023, 1, 31),
            }
        ])

        payslips.compute_sheet()
        payslips.action_payslip_done()
        payslips.action_payslip_paid()

        yearly_salary_report = self.env['yearly.salary.detail'].create({
            'year': '2023',
            'department_id': self.rd_dept.id,
        })

        action = yearly_salary_report.print_report()
        form_data = action['data']['form']

        self.assertEqual(form_data['employee_ids'], [self.jethalal_emp.id, self.rahul_emp.id], 'Employees with created payslips should be present in the report.')
        self.assertEqual(action['report_name'], 'l10n_in_hr_payroll.report_hryearlysalary')

        generated_report = self.env['ir.actions.report'].with_context(
            active_model='yearly.salary.detail',
            active_id=yearly_salary_report.id
        )._render('l10n_in_hr_payroll.report_hryearlysalary', yearly_salary_report.ids, data=action['data'])

        self.assertTrue(generated_report, 'Pdf report should be generated.')

    def test_l10n_in_salary_statement_report_creation(self):
        payslips = self.env['hr.payslip'].create([{
                'name': 'Jethalal Payslip',
                'employee_id': self.jethalal_emp.id,
                'version_id': self.contract_jethalal.id,
                'date_from': date(2023, 1, 1),
                'date_to': date(2023, 1, 31),
            }, {
                'name': 'Rahul Payslip',
                'employee_id': self.rahul_emp.id,
                'version_id': self.contract_rahul.id,
                'date_from': date(2023, 1, 1),
                'date_to': date(2023, 1, 31),
            }
        ])

        payslips.compute_sheet()
        payslips.action_payslip_done()
        payslips.action_payslip_paid()

        salary_statement_report = self.env['l10n_in_hr_payroll.salary.statement'].create({
            'name': 'Salary Statment Report',
            'year': '2023',
            'month': '1',
        })
        salary_statement_report.action_generate_declarations()
        declaration_lines = salary_statement_report.line_ids

        self.assertTrue(declaration_lines, 'Declaration lines should be generated')
        self.assertEqual(len(declaration_lines), 2, '2 declaration lines should be generated')

        # Generate PDFs
        declaration_lines._generate_pdf()

        self.assertTrue(
            all(line.state == 'pdf_generated' for line in declaration_lines),
            "PDF should be generated for all declaration lines.",
        )
