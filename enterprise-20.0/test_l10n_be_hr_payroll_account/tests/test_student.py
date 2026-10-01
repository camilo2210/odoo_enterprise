# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@tagged('post_install', '-at_install', 'student')
class TestStudent(TestPayslipValidationCommon, TestBelgiumCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
        })

        cls.env.user.group_ids |= cls.env.ref('hr.group_hr_user') | cls.env.ref('hr_payroll.group_hr_payroll_user')
        cls.new_calendar = cls.env['resource.calendar'].create({
            'name': 'O h/w calendar',
            'company_id': cls.env.company.id,
            'hours_per_day': 9,
            'full_time_required_hours': 0,
            'attendance_ids': [(5, 0, 0)],
        })

        cls.employee = cls.env['hr.employee'].sudo().create({
            'name': 'Jean-Pol Student',
            'company_id': cls.env.company.id,
            'resource_calendar_id': cls.new_calendar.id,
            'date_version': date(2015, 1, 1),
            'contract_date_start': date(2015, 1, 1),
            'l10n_be_dimona_category': 'stu',
            'wage': 0,
            'wage_type': 'hourly',
            'hourly_wage': 10.87,
            'fuel_card': 0,
            'meal_voucher_amount': 7.45,
            'commission_on_target': 0,
            'ip_wage_rate': 0,
            'private_car_employee_kilometer': 25,
            'distance_home_work': 25,
            'internet': 0,
            'mobile': 0,
        }).sudo(False)

        cls.contract = cls.employee.version_id

    def test_student(self):
        # CASE: Worked 6 days
        attendance_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_attendance').sudo()
        attendance_work_entry_type.requires_allocation = False
        attendance_work_entry_type.request_unit = 'hour'
        attendance_work_entry_type.count_as = 'working_time'
        self.env['hr.leave'].create([
            {
                'employee_id': self.employee.id,
                'work_entry_type_id': attendance_work_entry_type.id,
                'request_date_from': date(2020, 9, day),
                'request_date_to': date(2020, 9, day),
                'request_hour_from': 8,
                'request_hour_to': 17,
                'number_of_days': 1,
            } for day in [1, 2, 3, 4, 7, 8]
        ])

        payslip = self.env['hr.payslip'].with_context(allowed_company_ids=self.env.company.ids).create({
            'name': 'Test Payslip',
            'employee_id': self.employee.id,
            'date_from': date(2020, 9, 1),
            'date_to': date(2020, 9, 30),
        })

        self.assertEqual(len(payslip.worked_days_line_ids), 1)
        self.assertEqual(payslip.worked_days_line_ids.number_of_hours, 54)
        self.assertEqual(payslip.worked_days_line_ids.number_of_days, 6)

        payslip.compute_sheet()

        self._validate_payslip(payslip)
