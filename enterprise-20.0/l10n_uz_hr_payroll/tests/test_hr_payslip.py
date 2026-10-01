# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUzbekistanPayroll(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.structure = cls.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_structure')
        cls.structure_type = cls.env.ref('l10n_uz_hr_payroll.l10n_uz_employee_payroll_structure_type')
        cls.annual_leave_type = cls.env.ref('hr_work_entry.l10n_uz_work_entry_type_annual_labor_leave')
        cls.annual_leave_type_sunday = cls.env.ref('hr_work_entry.l10n_uz_work_entry_type_annual_labor_leave_sunday')

        cls.env.company.country_id = cls.env.ref('base.uz')
        cls.uz_company = cls.env.company

        work_entry_type = cls.env.ref('hr_work_entry.uz_work_entry_type_attendance')

        cls.calendar_5_days = cls.env['resource.calendar'].create({
            'name': "Standard 5 Days / 40 Hours",
            'company_id': cls.uz_company.id,
            'hours_per_day': 8.0,
            'attendance_ids': [(0, 0, {
                'dayofweek': str(i),
                'hour_from': 8.0,
                'hour_to': 16.0,
                'work_entry_type_id': work_entry_type.id,
            }) for i in range(5)],
        })

        cls.calendar_6_days = cls.env['resource.calendar'].create({
            'name': "Standard 6 Days / 40 Hours",
            'company_id': cls.uz_company.id,
            'hours_per_day': 6.67,
            'attendance_ids': [(0, 0, {
                'dayofweek': str(i),
                'hour_from': 9.0,
                'hour_to': 17.0,
                'work_entry_type_id': work_entry_type.id,
            }) for i in range(6)],
        })

        cls._setup_common(
            country=cls.env.ref('base.uz'),
            structure=cls.structure,
            structure_type=cls.structure_type,
            resource_calendar=cls.calendar_5_days,
            tz='UTC',
            employee_fields={
                'name': 'Employee 1 (Standard 5-Day)',
                'l10n_uz_annual_leave_eligibility': 21.0,
            },
            version_fields={
                'wage': 10_000_000.0,
                'contract_date_start': date(2023, 1, 1),
                'date_version': date(2023, 1, 1),
            },
        )

    def test_basic_salary_calculation_5_day_week(self):
        """
        Test if the basic salary for a standard 5-day week is calculated correctly.
        The company has the annual labor leave work entry type set, and the social tax class is "Taxpayer" (12%).
        The employee has a wage of 10,000,000 and is eligible for 21 days of annual leave.
        Checks:
        BASIC = 10.000.000
        GROSS = 10.000.000
        PENSION_FUND = 10.000 (0.1% of GROSS)
        ANNUAL_LEAVE_PROVISION = 691.699,60 (21/12 * 1 month * 10.000.000 / 25,3)
        SOCIAL_TAX_EMPLOYER = 1.200.000 (12% of GROSS)
        INCOME_TAX = -1.200.000 (12% of GROSS)
        NET = 8.800.000 (GROSS - INCOME_TAX)
        """
        standard_employee = self.employee

        payslip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=standard_employee.id,
        )
        self._validate_payslip(payslip)

    def test_basic_salary_calculation_6_day_week(self):
        """
        Test if the basic salary for a standard 6-day week is calculated correctly.
        The company has the annual labor leave work entry type set, and the social tax class is "Taxpayer" (12%).
        The employee has a wage of 10,000,000 and is eligible for 21 days of annual leave.
        Checks:
        BASIC = 10.000.000
        GROSS = 10.000.000
        PENSION_FUND = 10.000 (0.1% of GROSS)
        ANNUAL_LEAVE_PROVISION = 691.699,60 (21/12 * 1 month * 10.000.000 / 25,3)
        SOCIAL_TAX_EMPLOYER = 1.200.000 (12% of GROSS)
        INCOME_TAX = -1.200.000 (12% of GROSS)
        NET = 8.800.000 (GROSS - INCOME_TAX)
        """
        employee_6_day = self.env['hr.employee'].create({
            'name': 'Employee 2 (6-Day Week)',
            'company_id': self.uz_company.id,
            'resource_calendar_id': self.calendar_6_days.id,
            'l10n_uz_annual_leave_eligibility': 21.0,
            'wage': 10_000_000.0,
            'structure_type_id': self.structure_type.id,
            'contract_date_start': date(2023, 1, 1),
            'date_version': date(2023, 1, 1),
        })

        payslip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=employee_6_day.id,
            version_id=employee_6_day.current_version_id.id
        )
        self._validate_payslip(payslip)

    def test_mid_month_start_5_day(self):
        """
        When an employee contract starts in the middle of the month,
        the basic salary should be prorated based on the number of working days and actual
        worked days in that month.
        """
        employee_mid_month_5_day = self.env['hr.employee'].create({
            'name': 'Employee Mid Month (5-Day Week)',
            'company_id': self.uz_company.id,
            'resource_calendar_id': self.calendar_5_days.id,
            'l10n_uz_annual_leave_eligibility': 21.0,
            'wage': 10_000_000.0,
            'structure_type_id': self.structure_type.id,
            'contract_date_start': date(2026, 1, 16),
            'date_version': date(2026, 1, 16),
        })
        payslip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=employee_mid_month_5_day.id,
            version_id=employee_mid_month_5_day.current_version_id.id
        )
        # 11 days worked out of 22 days in January 2026 (5-day week) = 50% of the wage
        payslip_results = {'BASIC': 10000000 * 11 / 22}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_mid_month_start_6_day(self):
        """
        When an employee contract starts in the middle of the month,
        the basic salary should be prorated based on the number of working days and actual
        worked days in that month.
        """
        employee_mid_month_6_day = self.env['hr.employee'].create({
            'name': 'Employee Mid Month (6-Day Week)',
            'company_id': self.uz_company.id,
            'resource_calendar_id': self.calendar_6_days.id,
            'l10n_uz_annual_leave_eligibility': 21.0,
            'wage': 10_000_000.0,
            'structure_type_id': self.structure_type.id,
            'contract_date_start': date(2026, 1, 20),
            'date_version': date(2026, 1, 20),
        })
        payslip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=employee_mid_month_6_day.id,
            version_id=employee_mid_month_6_day.current_version_id.id
        )
        # 11 days worked out of 27 days in January 2026 (6-day week) = 40.74% of the wage
        payslip_results = {'BASIC': 10000000 * 11 / 27}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_company_different_tax_category(self):
        """
        Test that social tax amounts are computed correctly for companies with different tax categories.
        The social tax rate for the category 'Budgetary Organizations' is 25%.
        """
        self.uz_company.l10n_uz_social_tax_category = 'budgetary'

        payslip = self._generate_payslip(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
        payslip_results = {'SOCIAL_TAX_EMPLOYER': 10000000 * 0.25}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_different_annual_leave_eligibility(self):
        """
        Test that the annual leave provision scales with eligibility.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Employee 30 Days Annual leave',
            'company_id': self.uz_company.id,
            'resource_calendar_id': self.calendar_5_days.id,
            'wage': 10_000_000.0,
            'structure_type_id': self.structure_type.id,
            'contract_date_start': date(2026, 1, 1),
            'date_version': date(2026, 1, 1),
        })
        employee.current_version_id.l10n_uz_annual_leave_eligibility = 30.0

        payslip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=employee.id,
            version_id=employee.current_version_id.id,
        )
        payslip_results = {'ANNUAL_LEAVE_PROVISION': 988142.29}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_annual_labor_leave(self):
        """
        Test that average salary is computed correctly for an employee with no previous payslips
        and Sundays consume leaves but are unpaid.
        """
        self._generate_leave(self.employee, date(2026, 2, 13), date(2026, 2, 16), self.annual_leave_type)

        payslip = self._generate_payslip(date(2026, 2, 1), date(2026, 2, 28))

        # Since this employee has no historical payslips, average wage falls back to base_wage / 25.3
        expected_avg_daily = 10000000.0 / 25.3
        self.assertAlmostEqual(payslip.l10n_uz_average_daily_wage, expected_avg_daily, places=2)

        # Validate that Sunday generates a LABORLEAVESUN work entry and consumes leave, but does not pay the employee for that day.
        sunday_work_entry = payslip.worked_days_line_ids.filtered(lambda wd: wd.work_entry_type_id == self.annual_leave_type_sunday)
        self.assertEqual(sunday_work_entry.number_of_days, 1.0, "Sunday should consume 1 day of leave")
        self.assertEqual(sunday_work_entry.amount, 0.0, "Sunday should not pay the employee for that day, but should consume leave")

        # The remaining days should be paid at the average daily wage rate (including Saturday even though the employee has a 5-day work week)
        leave_work_entries = payslip.worked_days_line_ids.filtered(lambda wd: wd.work_entry_type_id == self.annual_leave_type)
        self.assertEqual(leave_work_entries.number_of_days, 3.0, "Friday, Saturday, and Monday should consume 3 days of leave")
        self.assertAlmostEqual(leave_work_entries.amount, 3.0 * expected_avg_daily, places=2, msg="Friday, Saturday, and Monday should be paid at the average daily wage rate")

    def test_average_daily_wage_fallback_no_history(self):
        """
        When an employee has no validated past payslips, average daily wage
        falls back to base_wage / 25.3.
        Wage = 10,000,000 UZS -> Daily = 395,256.92 UZS
        """
        payslip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=self.employee.id,
        )

        expected_daily_wage = 10_000_000.0 / 25.3
        expected_monthly_wage = expected_daily_wage * 25.3

        self.assertAlmostEqual(payslip.l10n_uz_average_daily_wage, expected_daily_wage, places=2)
        self.assertAlmostEqual(payslip.l10n_uz_average_monthly_wage, expected_monthly_wage, places=2)

    def test_average_wage_with_history_and_bonuses(self):
        """
        Test the average daily and monthly wage computation for an employee with historical payslips, including bonuses and allowances.
        The average wage computation should include all payments made to the employee during the past 12 months, including base salary, bonuses,
        and allowances, divided by the number of effective worked days.
        """
        # Payslip 1 (February 2026) - Bonuses
        past_slip = self._generate_payslip(
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
            employee_id=self.employee.id,
        )
        past_slip._set_input_value('BONUS', 2_000_000.0)
        past_slip.version_id._set_property_input_value('SENIORITY_SUPPLEMENT', 15.0)
        past_slip._set_input_value('OTHER_ALLOWANCE', 500_000.0)

        past_slip.compute_sheet()
        past_slip.action_validate()
        feb_avg_daily_wage = past_slip.version_id.l10n_uz_initial_average_monthly_wage / 25.3
        self.assertAlmostEqual(past_slip.l10n_uz_average_daily_wage, feb_avg_daily_wage, places=2)

        # Current Payslip (March 2026)
        current_payslip = self._generate_payslip(
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            employee_id=self.employee.id,
        )
        remun_past_12_months = past_slip.version_id.l10n_uz_initial_average_monthly_wage * 11 + past_slip.version_id.wage + 2000000 + 1500000 + 500000
        mar_avg_daily_wage = remun_past_12_months / (25.3 * 12)

        self.assertAlmostEqual(current_payslip.l10n_uz_average_daily_wage, mar_avg_daily_wage, places=2)
        self.assertAlmostEqual(current_payslip.l10n_uz_average_monthly_wage, mar_avg_daily_wage * 25.3, places=2)

    def test_average_wage_excludes_absences_and_absence_payments(self):
        """
        Test that partial months exclude absence days (like leaves) and payments for absence periods
        from the average wage computation per Art. 257.
        """
        # Payslip 1 (February 2026) - partial month due to leaves
        self._generate_leave(self.employee, date(2026, 2, 2), date(2026, 2, 6), self.annual_leave_type)
        past_slip_1 = self._generate_payslip(
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
            employee_id=self.employee.id,
        )
        past_slip_1._set_input_value('BONUS', 2_000_000.0)
        past_slip_1.compute_sheet()
        past_slip_1.action_validate()

        feb_avg_daily_wage = past_slip_1.version_id.l10n_uz_initial_average_monthly_wage / 25.3
        self.assertAlmostEqual(past_slip_1.l10n_uz_average_daily_wage, feb_avg_daily_wage, places=2)

        # Current Month (March 2026)
        current_payslip = self._generate_payslip(
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            employee_id=self.employee.id,
        )

        # Total paid amount = 11,476,284.58
        # Salary paid for working days = wage * (worked_days / scheduled_worked_days) = 10,000,000 * (15/20) = 7,500,000.00
        # Salary paid for leaves = 1,976,284.58
        # Total effective worked days = (25.3 / scheduled_days) * worked_days = (25.3 / 20) * 15 = 18.975
        # Total paid for working (including bonuses) = total_paid - total_paid_for_leaves = 11,476,284.58 - 1,976,284.58 = 9,500,000.00
        # Average daily wage = total_paid_for_working / effective_worked_days = 9,500,000.00 / 18.975 = 500,658.76
        mar_avg_daily_wage = (past_slip_1.version_id.l10n_uz_initial_average_monthly_wage * 11 + 9_500_000.00) / (25.3 * 11 + 18.975)

        self.assertAlmostEqual(current_payslip.l10n_uz_average_daily_wage, mar_avg_daily_wage, places=2)
        self.assertAlmostEqual(current_payslip.l10n_uz_average_monthly_wage, mar_avg_daily_wage * 25.3, places=2)

    def test_leave_overlapping_public_holiday(self):
        """
        Test that a public holiday overlapping with an annual leave request:
        1. Does not consume the employee's annual leave allocation.
        2. Is paid at the regular daily rate, while the actual leave days are paid at the average daily wage.
        """
        # Create a Public Holiday on Thursday, May 14, 2026
        public_holiday = self.env.ref('hr_work_entry.uz_work_entry_type_public_holiday')
        self.env['resource.calendar.leaves'].create({
            'name': 'Test Public Holiday',
            'calendar_id': self.calendar_5_days.id,
            'company_id': self.uz_company.id,
            'resource_id': False,
            'work_entry_type_id': public_holiday.id,
            'date_from': datetime(2026, 5, 14, 0, 0, 0),
            'date_to': datetime(2026, 5, 14, 23, 59, 59),
        })

        leave_allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation',
            'work_entry_type_id': self.annual_leave_type.id,
            'employee_id': self.employee.id,
            'number_of_days': 21.0,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 12, 31),
        })
        leave_allocation.action_approve()

        # Create leave overlapping the Public Holiday: Wed May 13 to Fri May 15
        leave = self.env['hr.leave'].with_context(tz='UTC').create({
            'name': 'Leave over Public Holiday',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.annual_leave_type.id,
            'request_date_from': date(2026, 5, 13),
            'request_date_to': date(2026, 5, 15),
        })
        leave.action_approve()

        # Only 2 days of leave should be consumed
        self.assertEqual(leave_allocation.virtual_remaining_leaves, 19.0, "Only 2 days of leave should be consumed because Thursday is a Public Holiday.")

        # Generate Payslip for May 2026
        payslip = self._generate_payslip(date(2026, 5, 1), date(2026, 5, 31))

        # Calculate Expected Values
        # Expected Average Daily Wage (No history -> Base Wage / 25.3)
        expected_average_daily_wage = payslip.version_id.l10n_uz_initial_average_monthly_wage / 25.3

        # Expected Regular Daily Rate (Base Wage / Scheduled working days in May 2026)
        # May 2026 has 21 scheduled working days (Monday-Friday)
        expected_regular_daily_wage = payslip.version_id.wage / 21.0

        leave_work_entries = payslip.worked_days_line_ids.filtered(lambda wd: wd.work_entry_type_id == self.annual_leave_type)
        self.assertEqual(leave_work_entries.number_of_days, 2.0, "There should be exactly 2 leaves.")
        self.assertAlmostEqual(leave_work_entries.amount, 2.0 * expected_average_daily_wage, places=2, msg="Leave should be paid at the average daily wage.")

        public_holiday_work_entries = payslip.worked_days_line_ids.filtered(lambda wd: wd.work_entry_type_id == public_holiday)
        self.assertEqual(public_holiday_work_entries.number_of_days, 1.0, "There should be exactly 1 public holiday.")
        self.assertAlmostEqual(public_holiday_work_entries.amount, expected_regular_daily_wage, places=2, msg="Public Holiday should be paid at the normal daily rate.")

    def test_departure_payslip(self):
        """
        Test Severance and Remaining Leaves on Departure.
        Employee started 2022-07-01 and leaving on 2026-01-16 (3 years, 6 months, 15 days).
        - Severance: For 3-4 years of service, the multiplier is 75% of the average monthly wage.
        - Remaining Leaves: Calculated as 12 days by the localization.
        """
        # Set the contract start date to July 7, 2022
        self.employee.current_version_id.write({
            'contract_date_start': date(2022, 7, 1),
            'date_version': date(2022, 7, 1),
        })

        departure_reason = self.env['hr.departure.reason'].create({
            'name': 'Test Departure With Severance',
            'l10n_uz_is_severance_paid': True,
        })

        # Register the departure (This natively caps the contract_date_end)
        self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'dismissal_date': date(2026, 1, 16),
            'departure_reason_id': departure_reason.id,
            'departure_description': 'Test Departure',
        }).action_register()

        # Generate Payslip
        payslip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=self.employee.id
        )
        payslip.compute_sheet()
        payslip.action_validate()

        self._validate_payslip(payslip)

    def test_batch_work_entry_generation(self):
        """
        Test that batch generation of work entries isolates covered dates by version.
        This prevents a bug where one employee's schedule (e.g., working on Sundays)
        accidentally suppresses the generation of Sunday leave entries for another
        employee processed in the same batch.
        """
        calendar_wed_sun = self.env['resource.calendar'].create({
            'name': "Wed-Sun Schedule",
            'company_id': self.uz_company.id,
            'hours_per_day': 8.0,
            'attendance_ids': [(0, 0, {
                'dayofweek': str(i),
                'hour_from': 8.0,
                'hour_to': 16.0,
                'work_entry_type_id': self.env.ref('hr_work_entry.uz_work_entry_type_attendance').id,
            }) for i in [2, 3, 4, 5, 6]],
        })

        employee_a = self.employee
        employee_b = self.env['hr.employee'].create({
            'name': 'Employee B (Sunday Worker)',
            'company_id': self.uz_company.id,
            'resource_calendar_id': calendar_wed_sun.id,
            'l10n_uz_annual_leave_eligibility': 21.0,
            'wage': 10_000_000.0,
            'structure_type_id': self.structure_type.id,
            'contract_date_start': date(2023, 1, 1),
            'date_version': date(2023, 1, 1),
        })

        self._generate_leave(employee_a, date(2026, 1, 9), date(2026, 1, 12), self.annual_leave_type)

        start_dt = datetime(2026, 1, 1, 0, 0, 0)
        end_dt = datetime(2026, 1, 31, 23, 59, 59)

        payslips = self.env['hr.payslip'].create([
            {
                'employee_id': employee_a.id,
                'date_from': start_dt,
                'date_to': end_dt,
                'version_id': employee_a.current_version_id.id,
                'struct_type_id': self.structure_type.id,
            },
            {
                'employee_id': employee_b.id,
                'date_from': start_dt,
                'date_to': end_dt,
                'version_id': employee_b.current_version_id.id,
                'struct_type_id': self.structure_type.id,
            },
        ])
        payslips.action_payslip_done()

        emp_a_sunday_leave = payslips.worked_days_line_ids.filtered(
            lambda wd: wd.employee_id == employee_a and wd.work_entry_type_id == self.annual_leave_type_sunday
        )
        emp_b_sunday_work = payslips.worked_days_line_ids.filtered(
            lambda wd: wd.employee_id == employee_b and wd.work_entry_type_id == self.env.ref('hr_work_entry.uz_work_entry_type_attendance')
        )

        self.assertTrue(emp_b_sunday_work, "Employee B should have a standard attendance entry on Sunday.")
        self.assertTrue(emp_a_sunday_leave, "Employee A should have an unpaid Sunday leave entry.")

    def test_wage_change_does_not_overwrite_initial_average_monthly_wage(self):
        """
        Check that changing regular contract wage doesn't overwrite initial avg wage.
        """
        version = self.employee.current_version_id
        version.l10n_uz_initial_average_monthly_wage = 12_000_000.0

        version.wage = 15_000_000.0

        self.assertEqual(
            version.l10n_uz_initial_average_monthly_wage,
            12_000_000.0,
            "Changing normal contract wage should not overwrite the initial average monthly wage once it has been explicitly set.",
        )

    def test_initial_wage_update_wizard(self):
        """
        Check that the wizard correctly updates the initial wage when launched via employee action.
        """
        version = self.employee.current_version_id
        version.l10n_uz_initial_average_monthly_wage = 10_000_000.0

        action = self.employee.action_open_initial_wage_update_wizard()
        self.assertEqual(action.get('res_model'), 'l10n.uz.average.monthly.wage.update.wizard')

        wizard = self.env['l10n.uz.average.monthly.wage.update.wizard'].create({
            'version_id': version.id,
            'new_initial_wage': 12_500_000.0,
            'reason': 'Forgot the extra baseline bonus.',
        })
        wizard.action_apply()

        self.assertEqual(
            version.l10n_uz_initial_average_monthly_wage,
            12_500_000.0,
            "Wizard should successfully update the initial average monthly wage.",
        )

    def test_existing_payslips_lock_wizard(self):
        """
        Check that having validated payslips in the last 12 months blocks wizard launch and execution with UserError.
        """
        # Validate a payslip within the last 12 months (e.g., January 2026)
        past_slip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=self.employee.id,
        )
        past_slip.compute_sheet()
        past_slip.action_validate()

        with self.assertRaises(UserError):
            self.employee.action_open_initial_wage_update_wizard()

    def test_payslips_older_than_12_months_do_not_block_wizard(self):
        """
        Check that validated payslips older than 12 months do not block the wizard from updating the wage.
        """
        old_slip = self._generate_payslip(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            employee_id=self.employee.id,
        )
        old_slip.compute_sheet()
        old_slip.action_validate()

        action = self.employee.action_open_initial_wage_update_wizard()
        self.assertEqual(action.get('res_model'), 'l10n.uz.average.monthly.wage.update.wizard')

        wizard = self.env['l10n.uz.average.monthly.wage.update.wizard'].create({
            'version_id': self.employee.current_version_id.id,
            'new_initial_wage': 12_500_000.0,
            'reason': 'Forgot the extra baseline bonus.',
        })
        wizard.action_apply()

        self.assertEqual(
            self.employee.current_version_id.l10n_uz_initial_average_monthly_wage,
            12_500_000.0,
            "Wizard should allow updates if all validated payslips are older than 12 months.",
        )

    def test_cancelled_payslips_do_not_block_wizard(self):
        """
        Check that cancelled payslips within the last 12 months DO NOT block the wizard.
        """
        cancelled_slip = self._generate_payslip(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            employee_id=self.employee.id,
        )
        cancelled_slip.compute_sheet()
        cancelled_slip.action_payslip_cancel()

        self.assertEqual(cancelled_slip.state, 'cancel')

        action = self.employee.action_open_initial_wage_update_wizard()
        self.assertEqual(action.get('res_model'), 'l10n.uz.average.monthly.wage.update.wizard')

        wizard = self.env['l10n.uz.average.monthly.wage.update.wizard'].create({
            'version_id': self.employee.current_version_id.id,
            'new_initial_wage': 15_000_000.0,
            'reason': 'Updating wage because the previous payslip was cancelled.',
        })
        wizard.action_apply()

        self.assertEqual(
            self.employee.current_version_id.l10n_uz_initial_average_monthly_wage,
            15_000_000.0,
            "Wizard should allow initial wage adjustments when existing payslips are cancelled.",
        )
