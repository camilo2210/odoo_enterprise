from datetime import date, datetime

from freezegun import freeze_time

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrPayrollHolidayAttest(TestPayrollCommon):

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.leaving_type_fired = self.env['hr.departure.reason'].create({
            'name': 'Fired',
            'l10n_be_reason_code': 342,
        })

        self.payslip_structure_type = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        self.struct_n_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        self.worker_code_015 = self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015')
        self.worker_employee_type = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_be_worker')

    def _create_employee(self, name):
        employee = self.env['hr.employee'].create({
            'name': name,
            'resource_calendar_id': self.resource_calendar.id,
            'contract_date_start': date(2025, 1, 1),
            'wage': 3000,
        })
        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'employee_id': employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': datetime(2026, 1, 1),
            'request_date_to': datetime(2026, 4, 30),
        })._action_validate()
        return employee

    def _create_departure(self, employee):
        return self.env['hr.employee.departure'].create({
            'employee_id': employee.id,
            'dismissal_date': '2026-06-11',
            'departure_date': '2026-07-01',
            'departure_reason_id': self.leaving_type_fired.id,
            'departure_description': 'Test',
        })

    def _create_attest_employee(self, worker=False):
        values = {
            'name': 'Attestation Employee',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'l10n_be_dimona_category': 'oth',
            'l10n_be_worker_code_id': (self.worker_code_015 if worker else self.worker_code_id).id,
        }
        if worker:
            values['employee_type_id'] = self.worker_employee_type.id
        return self.create_employee(values)

    def _create_attestation(self, employee, **values):
        attest_values = {
            'employee_id': employee.id,
            'attest_type': 'worker',
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 12, 31),
            'prev_work_hours_per_week': 38,
            'prev_reference_work_hours_per_week': 38,
            'prev_work_days_per_week': 5,
        }
        attest_values.update(values)
        if attest_values['attest_type'] == 'worker':
            attest_values.setdefault('prev_days_earned', 10)
            attest_values.setdefault('prev_total_holiday_pay_paid', 2000)
        else:
            attest_values.setdefault('prev_days_earned', 20)
            attest_values.setdefault('prev_simple_holiday_pay_paid', 1000)
            attest_values.setdefault('prev_double_holiday_pay_paid', 1000)
        return self.env['l10n.be.holiday.attest'].create(attest_values)

    def _create_regular_payslip_with_leave(self, attestation):
        attestation.leave_allocation_id.action_approve()
        self.env['hr.leave'].create({
            'name': 'Holiday Attestation Leave',
            'employee_id': attestation.employee_id.id,
            'work_entry_type_id': attestation.leave_allocation_id.work_entry_type_id.id,
            'request_date_from': date(2026, 1, 5),
            'request_date_to': date(2026, 1, 9),
        })._action_validate()
        payslip = self.env['hr.payslip'].create({
            'name': 'January 2026',
            'employee_id': attestation.employee_id.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
            'struct_id': self.payslip_structure_type.id,
        })
        payslip.compute_sheet()
        return payslip._get_line_values(['HolPayRec'])['HolPayRec'][payslip.id]['total']

    def _get_double_holiday_recovery(self, employee, year):
        payslip = self.env['hr.payslip'].create({
            'name': f'Double Holiday Pay {year}',
            'employee_id': employee.id,
            'date_from': date(year, 6, 1),
            'date_to': date(year, 6, 30),
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
        })
        payslip.compute_sheet()
        return payslip._get_line_values(['DOUBLERECOVERY'])['DOUBLERECOVERY'][payslip.id]['total']

    def _create_payslip(self, employee, date_from, date_to):
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'company_id': self.env.company.id,
            'struct_id': self.payslip_structure_type.id,
            'date_from': date_from,
            'date_to': date_to
        })
        payslip.action_validate()
        return payslip

    def _get_termination_payslip_values(self, employee):
        employee_departure = self._create_departure(employee)
        employee_departure._generate_termination_holidays()
        employee_departure_holiday_attest = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('struct_id', '=', self.struct_n_id.id)
        ], order='id desc', limit=1)
        payslip_values = employee_departure_holiday_attest._get_line_values(['PPTOTAL'])
        professional_tax = payslip_values['PPTOTAL'][employee_departure_holiday_attest.id]['total']
        return professional_tax

    def test_holiday_attest_witholding_tax_with_longterm_sick_leave(self):
        employee_with_sick_leave = self._create_employee('Employee Sick Leave')
        april_payslip = self._create_payslip(employee_with_sick_leave, datetime(2026, 4, 1), datetime(2026, 4, 30))

        april_payslip_basic = april_payslip._get_line_values(['BASIC'])['BASIC'][april_payslip.id]['total']
        self.assertEqual(april_payslip_basic, 0, "The basic salary should be zero for long sick leave after 30 days.")

        professional_tax = self._get_termination_payslip_values(employee_with_sick_leave)
        self.assertAlmostEqual(professional_tax, 148.87, places=2, msg="The professional tax should not be 0 even with long-term sick leave.")

    def test_holiday_attest_witholding_tax_with_longterm_sick_leave_and_bik(self):
        employee_with_sick_leave = self._create_employee('Employee 2 Sick Leave')
        employee_with_sick_leave.write({
            'internet': 50.0,
            'mobile': 50.0,
            'laptop': 50.0,
            'tablet': 50.0,
            'mobile_amount': 50.0,
        })

        april_payslip = self._create_payslip(employee_with_sick_leave, datetime(2026, 4, 1), datetime(2026, 4, 30))
        april_payslip_basic = april_payslip._get_line_values(['BASIC'])['BASIC'][april_payslip.id]['total']
        self.assertEqual(april_payslip_basic, 0, "The basic salary should be zero for long sick leave after 30 days.")

        professional_tax = self._get_termination_payslip_values(employee_with_sick_leave)
        self.assertEqual(professional_tax, 149.90, "The professional tax should not be 0 even with long-term sick leave.")

    def test_get_number_of_months(self):
        """Fractional month count within a single calendar year (dates are
        constrained to one year by _check_dates)."""
        Attest = self.env['l10n.be.holiday.attest']

        # Full single month -> 1.0
        att = Attest.new({'date_from': date(2024, 3, 1), 'date_to': date(2024, 3, 31)})
        self.assertAlmostEqual(att._get_number_of_months(), 1.0, places=6)

        # Partial single month, leap February (15 of 29 days)
        att = Attest.new({'date_from': date(2024, 2, 1), 'date_to': date(2024, 2, 15)})
        self.assertAlmostEqual(att._get_number_of_months(), 15 / 29, places=6)

        # Multi-month span: 15 Jan -> 20 Mar = 1 whole month + start/end fractions
        att = Attest.new({'date_from': date(2024, 1, 15), 'date_to': date(2024, 3, 20)})
        expected = 1 + (31 - 15 + 1) / 31 + 20 / 31
        self.assertAlmostEqual(att._get_number_of_months(), expected, places=6)

    def test_holiday_pay_caps_track_wage_and_daily_wage(self):
        """Double holiday pay is priced off the contract wage, simple holiday pay off the daily wage."""
        variable_calendar = self.env["resource.calendar"].create({
            "name": "Variable Calendar",
            "calendar_type": "variable",
            "days_per_week": 0.0,
            "hours_per_week": 38.0,
            "full_time_required_hours": 38,
            "company_id": self.belgian_company.id,
        })
        employee = self.create_employee({
            "name": "Hourly Variable",
            "date_version": date(2020, 1, 1),
            "contract_date_start": date(2020, 1, 1),
            "resource_calendar_id": variable_calendar.id,
            "wage_type": "hourly",
            "wage": 0,
            "hourly_wage": 25.0,
        })
        version = employee.version_id

        attestation = self.env["l10n.be.holiday.attest"].create({
            "employee_id": employee.id,
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 3, 31),
            "prev_work_hours_per_week": 38,
            "prev_reference_work_hours_per_week": 38,
            "prev_work_days_per_week": 5,
            "prev_assimilated_days": 60,
            "prev_simple_holiday_pay_paid": 500,
            "prev_double_holiday_pay_paid": 1000,
        })

        # An hourly wage on a variable calendar: there is a wage, but no hours to price a day with.
        self.assertTrue(
            attestation.has_contract_wage,
            "The attestation should have a contract wage, as the employee's hourly wage is set",
        )
        # 0.92 * (25.0 * 38 * 13 / 3) * min(1, 60 / (52 * 5)) = 874.0
        self.assertAlmostEqual(
            attestation.double_holiday_pay_cap,
            874.0,
            places=2,
            msg="The attestation should have a double holiday pay cap, as it is priced off the contract wage",
        )
        self.assertEqual(
            attestation.l10n_be_daily_wage,
            0,
            "The attestation should have no daily wage, as a variable calendar gives no hours per day to price one with",
        )
        self.assertEqual(
            attestation.simple_holiday_pay_cap,
            0,
            "The attestation should have no simple holiday pay cap, as it is priced off the daily wage",
        )

        version.resource_calendar_id = self.resource_calendar.id

        self.assertTrue(
            attestation.has_contract_wage,
            "The attestation should still have a contract wage, as the hourly wage is unchanged",
        )
        self.assertAlmostEqual(
            attestation.double_holiday_pay_cap,
            874.0,
            places=2,
            msg="The attestation should still have a double holiday pay cap, as the contract wage is unchanged",
        )
        self.assertEqual(
            attestation.l10n_be_daily_wage,
            190.0,
            "The attestation should have a daily wage, as the calendar now gives 7.6 hours per day at 25.0 per hour",
        )
        self.assertEqual(
            attestation.simple_holiday_pay_cap,
            500.0,
            "The attestation should have a simple holiday pay cap, capped at the amount the previous employer paid",
        )

        version.hourly_wage = 0

        self.assertFalse(
            attestation.has_contract_wage,
            "The attestation should have no contract wage, as the employee's hourly wage is cleared",
        )
        self.assertEqual(
            attestation.double_holiday_pay_cap,
            0,
            "The attestation should have no double holiday pay cap, as it is priced off the contract wage",
        )
        self.assertEqual(
            attestation.l10n_be_daily_wage,
            0,
            "The attestation should have no daily wage, as it is the hourly wage times the hours per day",
        )
        self.assertEqual(
            attestation.simple_holiday_pay_cap,
            0,
            "The attestation should have no simple holiday pay cap, as it is priced off the daily wage",
        )

    def test_holiday_pay_caps_match_for_equivalent_hourly_and_monthly_wages(self):
        """Paying a wage by the hour rather than by the month must not change what is recovered."""
        hourly_wage = 25.0
        # 38 hours a week, priced over the 13 / 3 weeks that make up a month.
        equivalent_monthly_wage = hourly_wage * 38 * 13 / 3
        hourly_employee = self.create_employee({
            "name": "Paid Hourly",
            "date_version": date(2020, 1, 1),
            "contract_date_start": date(2020, 1, 1),
            "wage_type": "hourly",
            "wage": 0,
            "hourly_wage": hourly_wage,
        })
        monthly_employee = self.create_employee({
            "name": "Paid Monthly",
            "date_version": date(2020, 1, 1),
            "contract_date_start": date(2020, 1, 1),
            "wage": equivalent_monthly_wage,
        })

        # The amounts paid by the previous employer are set high enough that both caps land on the
        # theoretical ceiling, which is what the wage feeds, rather than on the certificate amount.
        attestation_values = {
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 3, 31),
            "prev_work_hours_per_week": 38,
            "prev_reference_work_hours_per_week": 38,
            "prev_work_days_per_week": 5,
            "prev_assimilated_days": 60,
            "prev_simple_holiday_pay_paid": 50000,
            "prev_double_holiday_pay_paid": 50000,
        }
        Attestation = self.env["l10n.be.holiday.attest"]
        hourly_attestation = Attestation.create({**attestation_values, "employee_id": hourly_employee.id})
        monthly_attestation = Attestation.create({**attestation_values, "employee_id": monthly_employee.id})

        self.assertAlmostEqual(
            monthly_attestation.double_holiday_pay_cap,
            874.0,
            places=2,
            msg="The monthly employee should have a double holiday pay cap of 0.92 of their monthly wage, prorated",
        )
        self.assertAlmostEqual(
            hourly_attestation.l10n_be_daily_wage,
            monthly_attestation.l10n_be_daily_wage,
            places=2,
            msg="Both employees should have the same daily wage, as they are paid the same amount",
        )
        self.assertAlmostEqual(
            hourly_attestation.simple_holiday_pay_cap,
            monthly_attestation.simple_holiday_pay_cap,
            places=2,
            msg="Both employees should recover the same simple holiday pay, as it is priced off the daily wage",
        )
        self.assertAlmostEqual(
            hourly_attestation.double_holiday_pay_cap,
            monthly_attestation.double_holiday_pay_cap,
            places=2,
            msg="Both employees should recover the same double holiday pay, as it is priced off the monthly wage",
        )

    @freeze_time('2026-01-01')
    def test_worker_attestation_recovery_and_allocation(self):
        """A worker certificate grants employee leave and recovers holiday pay after solidarity."""
        former_worker = self._create_attest_employee()
        # 01/01-18/11/2025 = 322 calendar days -> 230 assimilated days (5d/week).
        # round(230 x 5/5 x 38/38) = 230 -> ONVA table 221-230 -> 19 days (employee formula would give 18).
        worker_attest = self._create_attestation(
            former_worker,
            date_from=date(2025, 1, 1),
            date_to=date(2025, 11, 18),
        )

        employee = self._create_attest_employee()
        self._create_attestation(employee, attest_type='employee')

        self.assertEqual(worker_attest.prev_total_holiday_pay_paid, 2000)
        self.assertFalse(worker_attest.is_worker)
        self.assertEqual(worker_attest.prev_simple_holiday_pay_paid, 1000)
        self.assertEqual(worker_attest.prev_double_holiday_pay_paid, 1000)
        self.assertAlmostEqual(worker_attest.limit_hours, 144.4)
        self.assertEqual(worker_attest.hours_to_allocate, 76)
        # 1% holiday-fund solidarity: 1000 x 0.99 = 990.
        self.assertEqual(worker_attest.simple_holiday_pay_cap, 990)
        self.assertEqual(worker_attest.leave_allocation_id.number_of_days, 10)
        self.assertEqual(worker_attest.leave_allocation_id.number_of_hours, 76)
        self.assertEqual(
            worker_attest.leave_allocation_id.work_entry_type_id,
            self.env.ref('hr_work_entry.be_work_entry_type_legal_leave'),
        )
        # 90% of 2500 x 3/13 recovered when the leave is taken.
        self.assertAlmostEqual(self._create_regular_payslip_with_leave(worker_attest), -519.23, places=2)
        self.assertEqual(self._get_double_holiday_recovery(former_worker, 2026), -990)
        # Employee certificates have no solidarity deduction.
        self.assertEqual(self._get_double_holiday_recovery(employee, 2026), -1000)

        january_payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', former_worker.id),
            ('date_from', '=', date(2026, 1, 1)),
        ], limit=1)
        january_payslip.action_payslip_done()
        december_payslip = self.env['hr.payslip'].create({
            'name': 'December 2026',
            'employee_id': former_worker.id,
            'date_from': date(2026, 12, 1),
            'date_to': date(2026, 12, 31),
            'struct_id': self.payslip_structure_type.id,
        })
        december_payslip.compute_sheet()
        holiday_pay_regularization = december_payslip._get_line_values(['HolPayReg'])['HolPayReg'][
            december_payslip.id
        ]['total']
        # Remaining 10% of 2500 x 3/13 recovered in December.
        self.assertAlmostEqual(holiday_pay_regularization, -57.69, places=2)

    @freeze_time('2026-01-01')
    def test_worker_attestation_for_current_worker(self):
        """A current worker receives worker leave without employer holiday-pay recovery."""
        worker = self._create_attest_employee(worker=True)
        attest = self._create_attestation(worker, prev_days_earned=25)

        self.assertTrue(attest.is_worker)
        self.assertEqual(attest.leave_allocation_id.number_of_days, 20)
        self.assertEqual(attest.leave_allocation_id.number_of_hours, 152)
        self.assertEqual(
            attest.leave_allocation_id.work_entry_type_id,
            self.env.ref('hr_work_entry.l10n_be_work_entry_type_worker_time_off'),
        )
        self.assertEqual(self._create_regular_payslip_with_leave(attest), 0)
        self.assertEqual(self._get_double_holiday_recovery(worker, 2026), 0)
