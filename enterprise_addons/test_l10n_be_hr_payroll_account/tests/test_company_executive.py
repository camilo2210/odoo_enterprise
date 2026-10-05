from datetime import date

from odoo.tests import tagged
from .common import TestPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCompanyExecutive(TestPayrollAccountCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attendance_work_entry_type = cls.env['hr.work.entry.type'].search([('code', '=', '002.00'), ('country_code', '=', 'BE')], limit=1)
        be_resource_calendar = cls.env['resource.calendar'].create({
            'name': 'BE Calendar',
            'company_id': cls.company_id.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(weekday),
                        'hour_from': hour,
                        'hour_to': hour + 4,
                        'work_entry_type_id': attendance_work_entry_type.id,
                       })
                for weekday in range(5)
                for hour in [8, 13]
            ],
        })
        cls.employee = cls.create_employee({
            'name': 'Karim',
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': False,
            'resource_calendar_id': be_resource_calendar.id,
        })

    def test_meal_vouchers_company_executive(self):
        self.employee.l10n_be_joint_committee_id = self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_999').id
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'date_from': date(date.today().year, 1, 1),
            'date_to': date(date.today().year, 1, 31),
            'struct_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
        })
        payslip.compute_sheet()
        number_of_attendances = payslip.worked_days_line_ids.filtered(lambda line: line.code == '002.00').number_of_days
        number_of_meal_vouchers = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'MEAL_V_EMP').quantity
        self.assertEqual(number_of_meal_vouchers, number_of_attendances)

        self.employee.version_id.fixed_meal_voucher_days = 30
        payslip.compute_sheet()
        number_of_attendances = payslip.worked_days_line_ids.filtered(lambda line: line.code == '002.00').number_of_days
        number_of_meal_vouchers = payslip.line_ids.filtered(lambda line: line.salary_rule_id.code == 'MEAL_V_EMP').quantity
        self.assertNotEqual(number_of_meal_vouchers, number_of_attendances)
        self.assertEqual(number_of_meal_vouchers, 30)
