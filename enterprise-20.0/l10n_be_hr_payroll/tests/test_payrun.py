from odoo.tests import tagged
from .common import TestPayrollCommon
from datetime import date


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollHrVersion(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.test_company = cls.env['res.company'].create({
            'name': 'Test Belgium Company',
            'country_id': cls.env.ref('base.be').id,
        })

        cls.be_monthly_structure = cls.env.ref("l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary")
        cls.be_double_holiday_structure = cls.env.ref("l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday")

        cls.test_emp = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'company_id': cls.test_company.id,
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'wage': 3000.0,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        })

        cls.work_entry_type_unpaid = cls.env['hr.work.entry.type'].create({
            'name': 'Unpaid Leave',
            'count_as': 'absence',
            'code': 'LEAVETEST300',
            'request_unit': 'half_day',
            'round_days_type': 'DOWN',
            'requires_allocation': False,
        })

        cls.employee_type = cls.env.ref('hr.contract_type_employee')

    def test_payrun_with_employee_multiple_version(self):
        employees = self.env['hr.employee'].create({
            'company_id': self.test_company.id,
            'date_version': date(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': date(2026, 1, 1),
            'name': "Multi Version Employee",
            'wage': 10000,
            'employee_type_id': self.employee_type.id,
        })

        multiple_versions = [
            {
                'date_version': date(2026, 1, 1),
                'contract_date_start': date(2026, 1, 1),
                'wage': 5000
            },
            {
                'date_version': date(2026, 1, 10),
                'contract_date_start': date(2026, 1, 1),
                'wage': 10000
            },
            {
                'date_version': date(2026, 1, 20),
                'contract_date_start': date(2026, 1, 1),
                'wage': 20000
            },
            {
                'date_version': date(2026, 1, 25),
                'contract_date_start': date(2026, 1, 1),
                'wage': 30000
            }
        ]

        for version in multiple_versions:
            employees.create_version(version)

        payrun_emp = self.env['hr.payslip.run'].create({
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'name': "Payrun Testing",
            'company_id': self.test_company.id,
            "structure_id": self.be_double_holiday_structure.id,
        })
        payrun_emp._generate_payslips()
        payrun_emp.action_validate()

        self.assertEqual(payrun_emp.state, '03_paid', "Payslip run should be in paid state.")
        self.assertTrue(payrun_emp.slip_ids, "Payslips should be generated for the payrun.")

        self.assertEqual(len(payrun_emp.slip_ids), 2, "Payslip count does not match the processed versions.")
