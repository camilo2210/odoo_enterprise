# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests.common import tagged

from odoo.addons.test_l10n_be_hr_payroll_account.tests.test_payslips_validation import TestPayslipValidation


@tagged('-at_install', 'post_install')  # LEGACY at_install
class TestDoubleHoliday(TestPayslipValidation, TestBelgiumCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def _create_calendar(cls, hours_per_week, full_time_hours_per_week=40.0, hours_per_day=None):
        hours_per_day = hours_per_day or (hours_per_week / 5.0)

        return cls.env['resource.calendar'].sudo().create({
            'name': f"{hours_per_week} Hours/Week",
            'company_id': cls.env.company.id,
            'hours_per_day': hours_per_day,
            'hours_per_week': hours_per_week,
            'full_time_required_hours': full_time_hours_per_week,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {
                    'dayofweek': str(day),
                    'hour_from': 8.0,
                    'hour_to': 8.0 + hours_per_day,
                    'work_entry_type_id': cls.env.ref(
                        'hr_work_entry.generic_work_entry_type_attendance'
                    ).id
                })
                for day in range(5)
            ],
        }).sudo(False)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.calendar_30_4h_per_week = cls.env['resource.calendar'].create({
            'name': '30.4h calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
            ]
        })

        partial_incapacity = cls.env.ref('hr_work_entry.l10n_be_work_entry_type_partial_incapacity')

        cls.calendar_15_12h_per_week_med = cls.env['resource.calendar'].create({
            'name': '15.12h med calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
            ]
        })

        cls.calendar_19h_per_week_med = cls.env['resource.calendar'].create({
            'name': '19h med calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
            ]
        })

        cls.calendar_22_8h_per_week_med = cls.env['resource.calendar'].create({
            'name': '22.8h med calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
            ]
        })

        cls.calendar_26_6h_per_week_med = cls.env['resource.calendar'].create({
            'name': '26.6h med calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
            ]
        })

        cls.calendar_30_4h_per_week_med = cls.env['resource.calendar'].create({
            'name': '30.4h med calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '0', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 3.8}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 3.8, 'work_entry_type_id': partial_incapacity.id}),
            ]
        })

        cls.env.ref('hr.structure_type_employee_cp200').default_resource_calendar_id = cls.company.resource_calendar_id

    def test_double_holidays(self):
        self.version.write({
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self.assertEqual(len(payslip.worked_days_line_ids), 0)

        self._validate_payslip(payslip)

    def test_double_holiday_no_right(self):
        self.version.contract_date_start = datetime.date(2021, 1, 1)
        self.version.date_version = datetime.date(2021, 1, 1)

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self.assertEqual(len(payslip.worked_days_line_ids), 0)

        self._validate_payslip(payslip)

    def test_double_holidays_incomplete_year_full_time(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 3, 15),
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_complete_year_credit_time(self):
        self.version.write({
            'resource_calendar_id': self.resource_calendar_4_5_wednesday_off_time_credit.id,
            'reference_calendar_id': self.resource_calendar_38_hours_per_week,
            'work_time_rate': 1.0,
            'wage': 2120.0,
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_incomplete_year_credit_time(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 3, 15),
            'resource_calendar_id': self.resource_calendar_4_5_wednesday_off_time_credit.id,
            'reference_calendar_id': self.resource_calendar_38_hours_per_week,
            'work_time_rate': 1.0,
            'wage': 2120.0,
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_complete_year_part_time(self):
        self.version.write({
            'resource_calendar_id': self.resource_calendar_38_hours_per_week.id,
            'wage': 2120.0,
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_incomplete_year_part_time(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 3, 15),
            'resource_calendar_id': self.resource_calendar_38_hours_per_week.id,
            'wage': 2120.0,
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_children_no_reduction(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 3, 15),
            'transport_mode_car': False,
        })

        self.employee.write({
            'children': 2,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_children_with_reductions(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 3, 15),
            'transport_mode_car': False,
        })

        self.employee.write({
            'children': 6,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        # This single employee's 6 children family deduction brings the theoretical tax to zero, so DH_PP is exempted.
        self._validate_payslip(payslip)

    def test_double_holidays_variable_revenues_complete_year(self):
        commission_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2020, 5, 1),
            'date_to': datetime.datetime(2020, 5, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        commission_payslip._set_input_value('COMMISSION', 3000)

        commission_payslip.action_refresh_from_work_entries()
        self.employee.write({'review_state': '1_reviewed'})
        commission_payslip.action_payslip_done()

        self.version.write({
            'commission_on_target': 1000,
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_variable_revenues_incomplete_year(self):
        commission_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2020, 5, 1),
            'date_to': datetime.datetime(2020, 5, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        commission_payslip._set_input_value('COMMISSION', 3000)
        commission_payslip.action_refresh_from_work_entries()
        self.employee.write({'review_state': '1_reviewed'})
        commission_payslip.action_payslip_done()

        self.version.write({
            'commission_on_target': 1000,
            'contract_date_start': datetime.date(2020, 3, 15),
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_variable_revenues_incomplete_year_with_attest(self):
        commission_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2020, 9, 1),
            'date_to': datetime.datetime(2020, 9, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        commission_payslip._set_input_value('COMMISSION', 6000)
        commission_payslip.action_refresh_from_work_entries()
        self.employee.write({'review_state': '1_reviewed'})
        commission_payslip.action_payslip_done()

        self.version.write({
            'commission_on_target': 1000,
            'contract_date_start': datetime.date(2020, 7, 1),
            'transport_mode_car': False,
        })
        self.version.employee_id.write({
            'l10n_be_fictive_hire_date': datetime.date(2020, 7, 1),
        })
        self.env["l10n.be.holiday.attest"].create([
            {
                "employee_id": self.employee.id,
                "date_from": datetime.date(2020, 1, 1),
                "date_to": datetime.date(2020, 6, 30),
                "prev_work_hours_per_week": 19,
                "prev_reference_work_hours_per_week": 38,
                "prev_work_days_per_week": 5,
                "prev_simple_holiday_pay_paid": 0,
                "prev_double_holiday_pay_paid": 1245.33,
            },
        ])

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_holiday_attest_40_over_38(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 7, 1),
            'transport_mode_car': False,
        })

        self.env["l10n.be.holiday.attest"].create([
            {
                "employee_id": self.employee.id,
                "date_from": datetime.date(2020, 1, 1),
                "date_to": datetime.date(2020, 6, 30),
                "prev_work_hours_per_week": 40,
                "prev_reference_work_hours_per_week": 38,
                "prev_work_days_per_week": 5,
                "prev_simple_holiday_pay_paid": 0,
                "prev_double_holiday_pay_paid": 1245.33,
            },
        ])

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_european_time_off(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 3, 15),
            'transport_mode_car': False,
        })

        self.employee.write({
            'children': 2,
        })

        self.env['hr.leave'].create({
            'name': 'European Time Off',
            'work_entry_type_id': self.european_time_off_type.id,
            'request_date_from': datetime.date(2020, 5, 4),
            'request_date_to': datetime.date(2020, 5, 4),
            'employee_id': self.employee.id,
        })

        european_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2020, 5, 1),
            'date_to': datetime.datetime(2020, 5, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        european_payslip.action_refresh_from_work_entries()
        self.employee.write({'review_state': '1_reviewed'})
        european_payslip.action_payslip_done()
        self.assertEqual(european_payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '142.20').amount, 122.31)

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holidays_european_time_off_over_2_years(self):
        self.version.write({
            'contract_date_start': datetime.date(2019, 1, 1),
            'transport_mode_car': False,
        })

        self.employee.write({
            'children': 2,
        })

        # Takes all the 4 weeks of european time off in Feb 2019
        # Should recover 2650 € in 2020
        self.env['hr.leave'].create({
            'name': 'European Time Off',
            'work_entry_type_id': self.european_time_off_type.id,
            'request_date_from': datetime.date(2019, 2, 1),
            'request_date_to': datetime.date(2019, 2, 28),
            'employee_id': self.employee.id,
        })

        european_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2019, 2, 1),
            'date_to': datetime.datetime(2019, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        european_payslip.action_refresh_from_work_entries()
        self.employee.write({'review_state': '1_reviewed'})
        european_payslip.action_payslip_done()
        self.assertEqual(european_payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '142.20').amount, 2650)

        payslip_2020 = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2020, 6, 1),
            'date_to': datetime.date(2020, 6, 30)
        })
        payslip_2020.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslip_2020.action_payslip_done()

        # We recover the maximum amount in 2020, and we should recover the remaining in 2021
        # 2650 - 2438 = 212 €
        self._validate_payslip(payslip_2020)

        payslip_2021 = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip_2021.compute_sheet()

        self._validate_payslip(payslip_2021)

    def test_double_holidays_company_car(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30)
        })
        payslip.compute_sheet()

        self.assertEqual(len(payslip.worked_days_line_ids), 0)

        self._validate_payslip(payslip)

    def test_double_holidays_pay_recovery(self):
        self.version.write({
            'transport_mode_car': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2021, 6, 1),
            'date_to': datetime.date(2021, 6, 30),
        })
        payslip._set_input_value('DOUBLERECOVERY', 438)
        payslip.compute_sheet()

        self.assertEqual(len(payslip.worked_days_line_ids), 0)

        self._validate_payslip(payslip)

    def test_double_holiday_recovery(self):
        self.version.write({
            'contract_date_start': datetime.date(2020, 8, 3),
            'wage': 1956.69,
        })

        self.env["l10n.be.holiday.attest"].create([
            {
                "employee_id": self.employee.id,
                "date_from": datetime.date(2020, 1, 1),
                "date_to": datetime.date(2020, 6, 30),
                "prev_work_hours_per_week": 38,
                "prev_reference_work_hours_per_week": 38,
                "prev_work_days_per_week": 5,
                "prev_simple_holiday_pay_paid": 0,
                "prev_double_holiday_pay_paid": 2781.82,
            }
        ])

        double_pay_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2021, 6, 1),
            'date_to': datetime.datetime(2021, 6, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': self.env.company.id,
        })
        double_pay_payslip._set_input_value('MONTH', 11)
        double_pay_payslip.compute_sheet()

        self.assertAlmostEqual(double_pay_payslip._get_input_line_amount('DOUBLERECOVERY'), 900.08, 2)

        self.assertEqual(len(double_pay_payslip.worked_days_line_ids), 0)

        self._validate_payslip(double_pay_payslip)

    def test_double_holiday_recovery_half_time_multi_attest(self):
        # Note: The employee was occupied with 2 half times over the same period
        self.version.write({
            'contract_date_start': datetime.date(2020, 8, 3),
            'wage': 2322.22,
        })

        self.env["l10n.be.holiday.attest"].create([
            {
                "employee_id": self.employee.id,
                "date_from": datetime.date(2020, 6, 1),
                "date_to": datetime.date(2020, 7, 31),
                "prev_assimilated_days": 45,
                "prev_simple_holiday_pay_paid": 0,
                "prev_double_holiday_pay_paid": 520.89,
                "prev_work_hours_per_week": 19,
                "prev_reference_work_hours_per_week": 38,
                "prev_work_days_per_week": 5,
            },
            {
                "employee_id": self.employee.id,
                "date_from": datetime.date(2020, 6, 1),
                "date_to": datetime.date(2020, 7, 31),
                "prev_assimilated_days": 45,
                "prev_simple_holiday_pay_paid": 0,
                "prev_double_holiday_pay_paid": 491.62,
                "prev_work_hours_per_week": 19,
                "prev_reference_work_hours_per_week": 38,
                "prev_work_days_per_week": 5,
            },
        ])
        double_pay_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2021, 6, 1),
            'date_to': datetime.datetime(2021, 6, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': self.env.company.id,
        })
        double_pay_payslip._set_input_value('MONTH', 7)
        double_pay_payslip.compute_sheet()

        self.assertAlmostEqual(double_pay_payslip._get_input_line_amount('DOUBLERECOVERY'), 369.76, 2)

        self.assertEqual(len(double_pay_payslip.worked_days_line_ids), 0)

        self._validate_payslip(double_pay_payslip)

    def test_double_holiday_recovery_multi_certificates_capped(self):
        """
        - Employee enters on 25/03/2024
        - Two holiday attests in 2023 with different regimes
        - Recovery must be capped to the computed entitlement
        """

        self.version.write({
            'contract_date_start': datetime.date(2024, 3, 25),
            'wage': 3750.00,
        })

        self.env['l10n.be.holiday.attest'].create([
            {
                'employee_id': self.employee.id,
                'date_from': datetime.date(2023, 1, 1),
                'date_to': datetime.date(2023, 10, 8),
                'prev_simple_holiday_pay_paid': 0,
                'prev_double_holiday_pay_paid': 5627.34,
                'prev_work_hours_per_week': 38,
                'prev_reference_work_hours_per_week': 38,
                'prev_work_days_per_week': 5,
            },
            {
                'employee_id': self.employee.id,
                'date_from': datetime.date(2023, 10, 9),
                'date_to': datetime.date(2023, 12, 31),
                'prev_simple_holiday_pay_paid': 0,
                'prev_double_holiday_pay_paid': 2075.60,
                'prev_work_hours_per_week': 36.66,
                'prev_reference_work_hours_per_week': 38,
                'prev_work_days_per_week': 5,
            },
        ])

        # Payslip
        double_pay_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2024, 6, 1),
            'date_to': datetime.datetime(2024, 6, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': self.env.company.id,
        })

        double_pay_payslip._set_input_value('MONTH', 12)
        double_pay_payslip.compute_sheet()

        # Expected recovery:
        # Total capped recovery = 3423.69
        # Remaining balance = 26.31 (taxable)
        self.assertAlmostEqual(
            double_pay_payslip._get_input_line_amount('DOUBLERECOVERY'),
            3421.93,
            2,
        )

        # No worked days expected
        self.assertEqual(len(double_pay_payslip.worked_days_line_ids), 0)

        self._validate_payslip(double_pay_payslip)

    def test_double_holiday_recovery_working_more_prorate_new_cap(self):
        """
        Employee works MORE now = limit using OLD smaller fraction

        We prorate:
        - Theoretical cap
        - New DP
        """

        # New job (2025)
        calendar_32h_40h = self._create_calendar(32)

        self.version.write({
            'resource_calendar_id': calendar_32h_40h.id,
            'contract_date_start': datetime.date(2025, 1, 1),
            'wage': 2500.00,
        })

        # Holiday attest from previous employer (2024)
        self.env['l10n.be.holiday.attest'].create([{
            'employee_id': self.employee.id,
            'date_from': datetime.date(2024, 1, 1),
            'date_to': datetime.date(2024, 12, 31),
            'prev_simple_holiday_pay_paid': 0,
            'prev_double_holiday_pay_paid': 4049.76,
            'prev_work_hours_per_week': 25,
            'prev_reference_work_hours_per_week': 38,
            'prev_work_days_per_week': 5,
        }])

        double_pay_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2025, 6, 1),
            'date_to': datetime.datetime(2025, 6, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref(
                'l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday'
            ).id,
            'company_id': self.env.company.id,
        })

        double_pay_payslip._set_input_value('MONTH', 12)
        double_pay_payslip.compute_sheet()

        # Expected recovery
        self.assertAlmostEqual(
            double_pay_payslip._get_input_line_amount('DOUBLERECOVERY'),
            1891.45,
            2
        )

        self.assertEqual(len(double_pay_payslip.worked_days_line_ids), 0)

        payslip_results = {
            'DOUBLERECOVERY': -1891.45,
            'DH_BASIC': 2300,
        }

        self._validate_payslip(double_pay_payslip, payslip_results, skip_lines=True)

    def test_double_holiday_recovery_working_less_prorate_old_certificate(self):
        """
        Rule 3:
        Employee works LESS now = prorate OLD certificate

        We prorate:
        - Certificate amount (downwards)
        - Then compare with new salary cap
        """
        calendar_30h_40h = self._create_calendar(30)

        # New job (2025) → smaller schedule
        self.version.write({
            'resource_calendar_id': calendar_30h_40h.id,
            'contract_date_start': datetime.date(2025, 1, 1),
            'wage': 2500.00,
        })

        # Holiday attest from previous employer (2024)
        self.env['l10n.be.holiday.attest'].create([{
            'employee_id': self.employee.id,
            'date_from': datetime.date(2024, 1, 1),
            'date_to': datetime.date(2024, 12, 31),
            'prev_simple_holiday_pay_paid': 0,
            'prev_double_holiday_pay_paid': 4417.92 / 2,
            'prev_work_hours_per_week': 32,
            'prev_reference_work_hours_per_week': 38,
            'prev_work_days_per_week': 5,
        }])

        double_pay_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2025, 6, 1),
            'date_to': datetime.datetime(2025, 6, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref(
                'l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday'
            ).id,
            'company_id': self.env.company.id,
        })

        double_pay_payslip._set_input_value('MONTH', 12)
        double_pay_payslip.compute_sheet()

        # Expected recovery
        self.assertAlmostEqual(
            double_pay_payslip._get_input_line_amount('DOUBLERECOVERY'),
            1967.36,
            2
        )

        self.assertEqual(len(double_pay_payslip.worked_days_line_ids), 0)

        payslip_results = {
            'DOUBLERECOVERY': -1967.36,
            'DH_BASIC': 2300,
        }

        self._validate_payslip(double_pay_payslip, payslip_results, skip_lines=True)

    def test_double_holidays_commission_first_incomplete_month(self):
        # If a payslip (first one or mid-month signing is incomplete and has commissions
        # take them into account
        self.version.write({
            'contract_date_start': datetime.date(2021, 12, 7),
            'commission_on_target': 1500,
        })
        self.version.employee_id.write({
            'l10n_be_fictive_hire_date': datetime.date(2021, 12, 7),
        })

        payslip = self._generate_payslip(datetime.date(2021, 12, 1), datetime.date(2021, 12, 31))
        payslip._set_input_value('COMMISSION', 300)
        payslip.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslip.action_payslip_done()

        double_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2022, 6, 1),
            'date_to': datetime.date(2022, 6, 30)
        })
        double_payslip.compute_sheet()

        self._validate_payslip(double_payslip)

    def test_double_holidays_full_time_credit_time(self):
        # Check that a full time credit time is not taken into account
        # on the number of occupation months
        self.version.write({
            'name': "Full Time Parental Time Off",
            'reference_calendar_id': self.resource_calendar_38_hours_per_week.id,
            'work_time_rate': 0,
            'wage': 2400,
            'resource_calendar_id': self.resource_calendar_0_hours_per_week.id,
            'contract_date_start': datetime.date(2021, 1, 1),
        })
        self.version.employee_id.write({
            'l10n_be_fictive_hire_date': datetime.date(2021, 1, 1),
        })

        double_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2022, 6, 1),
            'date_to': datetime.date(2022, 6, 30)
        })
        double_payslip.compute_sheet()

        self._validate_payslip(double_payslip)

    def test_double_holidays_european_time_off_current_year(self):
        # Check that european time off taken on the current year
        # are not recovered on the double holiday pay (and left for next year)

        self.env['hr.leave'].create({
            'name': 'European Time Off',
            'work_entry_type_id': self.european_time_off_type.id,
            'request_date_from': '2022-05-09',
            'request_date_to': '2022-05-12',
            'employee_id': self.employee.id,
        })

        european_payslip = self.env['hr.payslip'].create({
            'version_id': self.version.id,
            'date_from': datetime.datetime(2022, 5, 1),
            'date_to': datetime.datetime(2022, 5, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.env.company.id,
        })
        european_payslip.action_refresh_from_work_entries()
        self.employee.write({'review_state': '1_reviewed'})
        european_payslip.action_payslip_done()
        self.assertEqual(european_payslip.worked_days_line_ids.filtered(lambda wd: wd.code == '142.20').amount, 489.23)

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2022, 6, 1),
            'date_to': datetime.date(2022, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_case_01(self):
        self.version.write({
            'contract_date_start': datetime.date(2025, 1, 1),
            'date_version': datetime.date(2025, 1, 1),
            'wage': 2000,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_case_02(self):
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': datetime.date(2025, 6, 30),
            'wage': 2000,
        })

        part_time_version = self.env['hr.version'].create([{
            'date_version': datetime.date(2025, 7, 1),
            'contract_date_start': datetime.date(2025, 7, 1),
            'employee_id': self.version.employee_id.id,
            'resource_calendar_id': self.calendar_30_4h_per_week.id,
            'wage': 1500,
        }])

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': part_time_version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_case_03(self):
        self.version.write({
            'contract_date_start': datetime.date(2025, 7, 1),
            'date_version': datetime.date(2025, 7, 1),
            'wage': 2000,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_case_04(self):
        self.version.write({
            'contract_date_start': datetime.date(2025, 9, 15),
            'date_version': datetime.date(2025, 9, 15),
            'wage': 2000,
        })
        # Holiday attest from previous employer (2024)
        self.env['l10n.be.holiday.attest'].create([{
            'employee_id': self.employee.id,
            'date_from': datetime.date(2025, 1, 1),
            'date_to': datetime.date(2025, 5, 25),
            'prev_simple_holiday_pay_paid': 0,
            'prev_double_holiday_pay_paid': 2781.82,
            'prev_work_hours_per_week': 38,
            'prev_reference_work_hours_per_week': 38,
            'prev_work_days_per_week': 5,
        }])

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_case_05(self):
        self.version.write({
            'contract_date_start': datetime.date(2025, 9, 15),
            'date_version': datetime.date(2025, 9, 15),
            'wage': 2000,
        })

        self.env['l10n.be.holiday.attest'].create([{
            'employee_id': self.employee.id,
            'date_from': datetime.date(2025, 1, 1),
            'date_to': datetime.date(2025, 5, 25),
            'prev_simple_holiday_pay_paid': 0,
            'prev_double_holiday_pay_paid': 2781.82,
            'prev_work_hours_per_week': 38 * 0.7895,
            'prev_reference_work_hours_per_week': 38,
            'prev_work_days_per_week': 5,
        }])

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_case_06(self):
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Unpaid leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
            'request_date_from': datetime.date(2025, 1, 1),
            'request_date_to': datetime.date(2025, 1, 8),
            'employee_id': self.employee.id,
        })

        self.env['hr.leave'].with_context(skip_allocation_check=True).create({
            'name': 'Unjustified leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_unjustified_reason').id,
            'request_date_from': datetime.date(2025, 2, 1),
            'request_date_to': datetime.date(2025, 2, 8),
            'employee_id': self.employee.id,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 3, 1),
            'request_date_to': datetime.date(2025, 3, 8),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # The computation basis for the double and double complementary should be:
        #   ((23/31)/12 + (20/28)/12 + 10/12) * 2000 = 1909.37€
        #   DOUBLE = 1909.37 * 0.85 = 1622.96€
        #   DOUBLE_COMPLEMENTARY = 1909.37 * 0.07 = 133.66€
        self._validate_payslip(payslip)

    def test_double_holiday_case_07(self):
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 6, 10),
            'request_date_to': datetime.date(2025, 9, 15),
            'employee_id': self.employee.id,
        })

        self.env['hr.leave'].create({
            'name': 'Unpaid leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
            'request_date_from': datetime.date(2025, 9, 30),
            'request_date_to': datetime.date(2025, 10, 8),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # The computation basis for the double and double complementary should be:
        #   (5/12 + (9/30)/12 + (14/30)/12 + (23/31)/12 + 2/12) * 2000 = 1418.10€
        #   DOUBLE = 1418.10 * 0.85 = 1205.39€
        #   DOUBLE_COMPLEMENTARY = 1418.10 * 0.07 = 99.27€
        self._validate_payslip(payslip)

    def test_double_holiday_case_08(self):
        self.version.write({
            'contract_date_start': datetime.date(2025, 9, 1),
            'date_version': datetime.date(2025, 9, 1),
            'wage': 4000,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_case_09(self):
        self.version.write({
            'contract_date_start': datetime.date(2025, 3, 2),
            'date_version': datetime.date(2025, 3, 2),
            'wage': 3000,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        self._validate_payslip(payslip)

    def test_double_holiday_12_months_sickness(self):
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 1, 1),
            'request_date_to': datetime.date(2025, 12, 31),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # Double holiday should be full as first 12 months of sickness are taken into account
        self._validate_payslip(payslip)

    def test_double_holiday_13_months_sickness(self):
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 12, 1),
            'request_date_to': datetime.date(2025, 12, 31),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # Double holiday should be prorated as only the first 12 months of sickness are taken into account
        # The computation basis for the double and double complementary should be:
        #   (11/12) * 2000 = 1833.33€
        #   DOUBLE = 1909.37 * 0.85 = 1558.33€
        #   DOUBLE_COMPLEMENTARY = 1909.37 * 0.07 = 128.33€
        self._validate_payslip(payslip)

    def test_double_holiday_24_months_sickness(self):
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 1, 1),
            'request_date_to': datetime.date(2025, 12, 31),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # Double holiday should be zero as only the first 12 months of sickness are taken into account
        self._validate_payslip(payslip)

    def test_double_holiday_sickness_relapse_chain_over_12_months(self):
        """Two sick leaves linked by the relapse flag form a single chain.

        Leave A: Jan 1 2024 - Sep 30 2024  (9 months)
        Leave B: Oct 10 2024 - Dec 31 2025  (marked as relapse, within 14-day window)

        Chain origin = Jan 1 2024, 12-month cutoff = Jan 1 2025 + 10 days from back to work
        """
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave A',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 1, 1),
            'request_date_to': datetime.date(2024, 9, 30),
            'employee_id': self.employee.id,
        })

        last_sick_leave = self.env['hr.leave'].search([('employee_id', '=', self.employee.id)]).sorted('request_date_from')[-1]

        self.env['hr.leave'].create({
            'name': 'Sick leave B (relapse)',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 10, 10),
            'request_date_to': datetime.date(2025, 12, 31),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': last_sick_leave.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # Basis = 9/31/12 * 2000 = 48.39€
        # DOUBLE = 48.39 * 0.85 = 41.13€
        # DOUBLE_COMPLEMENTARY = 48.39 * 0.07 = 3.39€
        self._validate_payslip(payslip)

    def test_double_holiday_sickness_no_relapse_new_chain(self):
        """Two sick leaves within the relapse window but the second is NOT marked as a relapse.

        Leave A: Jan 1 2025 - Mar 31 2025  (3 months)
        Leave B: Apr 10 2025 - Dec 31 2025  (within 14 days of A, but NOT a relapse)

        Because B is not a relapse, it starts a fresh chain.  Both chains are < 12 months
        so every sick day in 2025 is assimilated → double holiday is full.
        """
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave A',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 1, 1),
            'request_date_to': datetime.date(2025, 3, 31),
            'employee_id': self.employee.id,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave B (NOT a relapse)',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 4, 10),
            'request_date_to': datetime.date(2025, 12, 31),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': False,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # Both chains < 12 months → full assimilation
        self._validate_payslip(payslip)

    def test_double_holiday_unpaid_leave_spanning_two_months(self):
        """An unpaid leave that straddles a month boundary must be split correctly.

        Leave: Jan 25 - Feb 5 2025 (unpaid)
          → Jan deduction: 7 calendar days (Jan 25-31)
          → Feb deduction: 5 calendar days (Feb 1-5)
        """
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Unpaid leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
            'request_date_from': datetime.date(2025, 1, 25),
            'request_date_to': datetime.date(2025, 2, 5),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # Basis = (24/31 + 23/28 + 10) / 12 * 2000 = 1932.60€
        # DOUBLE = 1932.60 * 0.85 = 1642.71€
        # DOUBLE_COMPLEMENTARY = 1932.60 * 0.07 = 135.28€
        self._validate_payslip(payslip)

    def test_double_holiday_sickness_cutoff_at_month_boundary(self):
        """Sick leave chain whose 12-month cutoff falls exactly on a month boundary.

        Leave: Feb 1 2024 - Dec 31 2025  (single leave)
        Chain origin = Feb 1 2024, 12-month cutoff = Feb 1 2025.

        In 2025:
          - Jan 2025 (before cutoff): fully assimilated → no deduction
          - Feb 1 2025 onwards: non-assimilated

        Non-assimilated days in 2025:
          Feb: 28 days, Mar-Dec: 10 full months

        Assimilated months: only January (1/12).
        """
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 2, 1),
            'request_date_to': datetime.date(2025, 12, 31),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # The computation basis for the double and double complementary should be:
        #   BASIS = 1/12 * 2000 = 166.67€
        #   DOUBLE = 166.67 * 0.85 = 141.67€
        #   DOUBLE_COMPLEMENTARY = 166.67 * 0.07 = 11.67€
        self._validate_payslip(payslip)

    def test_double_holiday_sickness_back_to_work(self):
        """Relapse chain that crosses the 12-month boundary after a brief return to work.

        Leave A: Mar 1 2024 - Feb 1 2025  (chain origin = Mar 1 2024)
        Leave B: Feb 10 2025 - Feb 16 2025  (relapse within 14-day window)
        Leave C: Mar 1 2025 - Dec 31 2025  (relapse)
        """
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 3, 1),
            'request_date_to': datetime.date(2025, 2, 1),
            'employee_id': self.employee.id,
        })

        last_sick_leave = self.env['hr.leave'].search([('employee_id', '=', self.employee.id)]).sorted('request_date_from')[-1]

        sick_leave_2 = self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 2, 10),
            'request_date_to': datetime.date(2025, 2, 16),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': last_sick_leave.id,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 3, 1),
            'request_date_to': datetime.date(2025, 12, 31),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': sick_leave_2.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        payslip.compute_sheet()

        # The computation basis for the double and double complementary should be:
        #   BASIS = 2/12 + 20/31/12 * 2000 = 440.86€
        #   DOUBLE = 440.86 * 0.85 = 374.73€
        #   DOUBLE_COMPLEMENTARY = 440.86 * 0.07 = 30.86€
        self._validate_payslip(payslip)

    def test_part_time_med_01(self):
        self.version.write({
            'date_version': datetime.date(2024, 4, 1),
            'contract_date_start': datetime.date(2024, 4, 1),
            'contract_date_end': datetime.date(2025, 5, 4),
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 5, 5),
            'contract_date_start': datetime.date(2025, 5, 5),
            'contract_date_end': datetime.date(2025, 6, 6),
            'resource_calendar_id': self.calendar_19h_per_week_med.id,
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 6, 7),
            'contract_date_start': datetime.date(2025, 6, 7),
            'contract_date_end': datetime.date(2025, 9, 24),
            'resource_calendar_id': self.calendar_26_6h_per_week_med.id,
        })

        latest_version = self.employee.create_version({
            'date_version': datetime.date(2025, 9, 25),
            'contract_date_start': datetime.date(2025, 9, 25),
            'contract_date_end': False,
            'resource_calendar_id': self.calendar_30_4h_per_week_med.id,
            'wage': 3276.77
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': latest_version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        self.assertAlmostEqual(payslip._l10n_be_get_paid_double_holiday(), 3276.77, 2)

    def test_part_time_med_02(self):
        self.version.write({
            'date_version': datetime.date(2024, 8, 1),
            'contract_date_start': datetime.date(2024, 8, 1),
            'contract_date_end': datetime.date(2025, 8, 24),
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 8, 25),
            'contract_date_start': datetime.date(2025, 8, 25),
            'contract_date_end': datetime.date(2025, 12, 31),
            'resource_calendar_id': self.calendar_19h_per_week_med.id,
        })

        latest_version = self.employee.create_version({
            'date_version': datetime.date(2026, 1, 1),
            'contract_date_start': datetime.date(2026, 1, 1),
            'contract_date_end': False,
            'resource_calendar_id': self.calendar_30_4h_per_week.id,
            'wage': 1981.49,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': latest_version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        self.assertAlmostEqual(payslip._l10n_be_get_paid_double_holiday(), 1981.49, 2)

    def test_part_time_med_03(self):
        self.version.write({
            'date_version': datetime.date(2024, 1, 1),
            'contract_date_start': datetime.date(2024, 1, 1),
            'contract_date_end': datetime.date(2025, 9, 21),
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 9, 22),
            'contract_date_start': datetime.date(2025, 9, 22),
            'contract_date_end': datetime.date(2025, 11, 23),
            'resource_calendar_id': self.calendar_15_12h_per_week_med.id,
            'work_time_rate': 1.0,
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 11, 24),
            'contract_date_start': datetime.date(2025, 11, 24),
            'contract_date_end': datetime.date(2026, 1, 25),
            'resource_calendar_id': self.calendar_22_8h_per_week_med.id,
            'work_time_rate': 1.0,
        })

        latest_version = self.employee.create_version({
            'date_version': datetime.date(2026, 1, 26),
            'contract_date_start': datetime.date(2026, 1, 26),
            'contract_date_end': False,
            'resource_calendar_id': self.calendar_30_4h_per_week_med.id,
            'work_time_rate': 1.0,
            'wage': 3711.22,
        })

        sick_leave1 = self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 1, 3),
            'request_date_to': datetime.date(2024, 1, 12),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 1, 24),
            'request_date_to': datetime.date(2024, 2, 29),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': sick_leave1.id,
        })

        last_sick_leave = self.env['hr.leave'].search([('employee_id', '=', self.employee.id)]).sorted('request_date_from')[-1]

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 3, 6),
            'request_date_to': datetime.date(2024, 5, 3),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': last_sick_leave.id,
        })

        last_sick_leave = self.env['hr.leave'].search([('employee_id', '=', self.employee.id)]).sorted('request_date_from')[-1]

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 5, 6),
            'request_date_to': datetime.date(2025, 1, 31),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': last_sick_leave.id,
        })

        last_sick_leave = self.env['hr.leave'].search([('employee_id', '=', self.employee.id)]).sorted('request_date_from')[-1]

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 2, 3),
            'request_date_to': datetime.date(2025, 9, 21),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': last_sick_leave.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': latest_version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        self.assertAlmostEqual(payslip._l10n_be_get_paid_double_holiday(), 1242.20, 2)

    def test_part_time_med_04(self):
        self.version.write({
            'date_version': datetime.date(2024, 3, 1),
            'contract_date_start': datetime.date(2024, 3, 1),
            'contract_date_end': datetime.date(2024, 12, 31),
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': datetime.date(2025, 7, 31),
            'resource_calendar_id': self.calendar_19h_per_week_med.id,
            'work_time_rate': 1.0,
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 8, 1),
            'contract_date_start': datetime.date(2025, 8, 1),
            'contract_date_end': datetime.date(2025, 8, 19),
            'resource_calendar_id': self.employee.company_id.resource_calendar_id.id,
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 8, 20),
            'contract_date_start': datetime.date(2025, 8, 20),
            'contract_date_end': datetime.date(2026, 2, 28),
            'resource_calendar_id': self.calendar_19h_per_week_med.id,
            'work_time_rate': 1.0,
        })

        latest_version = self.employee.create_version({
            'date_version': datetime.date(2026, 3, 1),
            'contract_date_start': datetime.date(2026, 3, 1),
            'contract_date_end': False,
            'resource_calendar_id': self.calendar_30_4h_per_week.id,
            'wage': 3616.76,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 10, 10),
            'request_date_to': datetime.date(2024, 12, 31),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
        })

        origin_leave = self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 6, 19),
            'request_date_to': datetime.date(2025, 7, 31),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 8, 1),
            'request_date_to': datetime.date(2025, 8, 19),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': origin_leave.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': latest_version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        self.assertAlmostEqual(payslip._l10n_be_get_paid_double_holiday(), 3616.76, 2)

    def test_part_time_med_05(self):
        self.version.write({
            'date_version': datetime.date(2024, 7, 1),
            'contract_date_start': datetime.date(2024, 7, 1),
            'contract_date_end': datetime.date(2025, 4, 30),
            'resource_calendar_id': self.calendar_30_4h_per_week.id,
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 5, 1),
            'contract_date_start': datetime.date(2025, 5, 1),
            'contract_date_end': datetime.date(2025, 8, 31),
            'resource_calendar_id': self.calendar_15_12h_per_week_med.id,
            'work_time_rate': 1.0,
        })

        self.employee.create_version({
            'date_version': datetime.date(2025, 9, 1),
            'contract_date_start': datetime.date(2025, 9, 1),
            'contract_date_end': datetime.date(2025, 10, 23),
            'resource_calendar_id': self.calendar_30_4h_per_week.id,
        })

        latest_version = self.employee.create_version({
            'date_version': datetime.date(2025, 10, 24),
            'contract_date_start': datetime.date(2025, 10, 24),
            'contract_date_end': False,
            'resource_calendar_id': self.calendar_22_8h_per_week_med.id,
            'work_time_rate': 1.0,
            'wage': 2303.61,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2024, 12, 31),
            'request_date_to': datetime.date(2024, 12, 31),
            'employee_id': self.employee.id,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 1, 1),
            'request_date_to': datetime.date(2025, 4, 30),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 7, 14),
            'request_date_to': datetime.date(2025, 8, 31),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
        })

        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime.date(2025, 9, 1),
            'request_date_to': datetime.date(2025, 10, 23),
            'employee_id': self.employee.id,
            'l10n_be_sickness_relapse': True,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': latest_version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        self.assertAlmostEqual(payslip._l10n_be_get_paid_double_holiday(), 2083.16, 2)

    def test_long_unpaid_leave(self):
        self.version.write({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 5805.46,
        })

        self.env['hr.leave'].create({
            'name': 'Unpaid leave',
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
            'request_date_from': datetime.date(2025, 3, 31),
            'request_date_to': datetime.date(2027, 3, 30),
            'employee_id': self.employee.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'company_id': self.env.company.id,
            'vehicle_id': self.car.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'date_from': datetime.date(2026, 6, 1),
            'date_to': datetime.date(2026, 6, 30)
        })
        self.assertAlmostEqual(payslip._l10n_be_get_paid_double_holiday(), 1435.76, 2)
