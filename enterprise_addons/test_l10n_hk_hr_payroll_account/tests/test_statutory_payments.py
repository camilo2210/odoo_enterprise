# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from odoo.tests import tagged
from odoo import Command

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestStatutoryPayments(TestL10NHkHrPayrollAccountCommon):
    _test_user_groups = (
        'hr_payroll.group_hr_payroll_user',
        'hr_payroll.group_hr_payroll_manager',  # To activate/deactivate the salary rules in some tests
        'base.group_erp_manager',  # A test require changing the company settings
    )

    @classmethod
    def setUpClass(cls):
        """
        Set up the test data that will be used for all statutory payment tests (Payment in Lieu of notice, Severance pay,
        long service pay, end of year pay).

        We need for that:
        - One profile with a high wage/long history.
        - One profile with a few years of employement.
        - One profile with a short employement.

        For payslips, we need one snapshot in April/May 2025 (For the termination payment split tests) and 12 months
        of payslips before the termination (for Payment in Lieu).
        """
        super().setUpClass()

        cls.veteran = cls._setup_employee(
            country=cls.env.ref('base.hk'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2000, 1, 1),
                'contract_date_start': date(2000, 1, 1),
                'contract_date_end': date(2026, 12, 31),
                'wage': 60000.0,
                'l10n_hk_member_class_id': cls.member_class.id,
            },
            employee_fields={'name': 'The Veteran'}
        )
        cls.mid_timer = cls._setup_employee(
            country=cls.env.ref('base.hk'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2025, 6, 1),
                'contract_date_start': date(2025, 6, 1),
                'contract_date_end': date(2028, 12, 31),
                'wage': 22500.0,
                'l10n_hk_member_class_id': cls.member_class.id,
            },
            employee_fields={'name': 'The Mid-Timer'}
        )
        cls.rookie = cls._setup_employee(
            country=cls.env.ref('base.hk'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2026, 1, 15),  # Purposefully starts in the middle of a month
                'contract_date_start': date(2026, 1, 15),
                'contract_date_end': date(2026, 10, 31),
                'wage': 18000.0,
                'l10n_hk_member_class_id': cls.member_class.id,
            },
            employee_fields={'name': 'The Rookie'}
        )
        # The mid-timer will have some leaves and some commissions set up for the tests.
        cls._generate_leave(
            cls.mid_timer,
            date(2028, 11, 13),
            date(2028, 11, 17),
            cls.env.ref('hr_work_entry.hk_work_entry_type_unpaid_leave'),
        )
        cls._generate_leave(
            cls.mid_timer,
            date(2028, 10, 9),
            date(2028, 10, 13),
            cls.env.ref('hr_work_entry.hk_work_entry_type_unpaid_leave'),
        )
        rule = cls.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_fixed_commission')
        rule.input_usage_employee = True
        cls.mid_timer.version_id._set_property_input_value('COMMISSION', 10000)

        required_periods = [
            (date(2025, 4, 1), date(2025, 5, 31)),   # Transition wage snapshot
            # Combined Veteran + Rookie periods (Oct 2025 to Nov 2026)
            (date(2025, 10, 1), date(2026, 11, 30)),
            # Mid-Timer departs Dec 2028 -> generate Dec 2027 to Nov 2028
            (date(2027, 12, 1), date(2028, 11, 30)),
        ]
        payruns_data = []
        for start_date, end_date in required_periods:
            for dt in rrule(MONTHLY, dtstart=start_date, until=end_date):
                payruns_data.append({
                    'name': dt.strftime('%B %Y'),
                    'date_start': dt.date(),
                    'date_end': dt.date() + relativedelta(day=31),
                    'company_id': cls.env.company.id,
                    'structure_id': cls.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
                })

        payruns = cls.env['hr.payslip.run'].create(payruns_data)
        for payrun in payruns.sorted('date_start asc'):
            payrun._generate_payslips()
        payruns.action_validate()

    ######################
    # Termination Payments
    ######################

    def _setup_termination_and_last_payslip(self, employee, termination_reason):
        """
        Set up a departure for the given employee on their contract end date (set during setUpClass); for the given
        termination reason then create a payslip in the departure month and return it.
        """
        self.env['hr.employee.departure'].create([{
            'employee_id': employee.id,
            'dismissal_date': employee.contract_date_end,
            'departure_reason_id': self.env.ref(termination_reason).id,
        }])

        return self._generate_payslip(
            date_from=employee.contract_date_end + relativedelta(day=1),
            date_to=employee.contract_date_end + relativedelta(day=31),
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )

    def test_termination_payment_post_transition(self):
        """
        Validate calculation of severance payment for an employment period starting after May 2025.
        Focus on the presence of the rule and their total and not the whole payslip.

        Validated against the calculator: https://www.offsettingsubsidy.gov.hk/en/calculator.html
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.mid_timer,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        result = {
            'TERMINATION_PAYMENT_POST_TRANSITION': 53794.52,
            'TERMINATION_PAYMENT': 53794.52,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    def test_termination_payment_pre_post_transition(self):
        """
        Validate calculation of severance payment for an employment period starting before May 2025.
        Focus on the presence of the rule and their total and not the whole payslip.

        Also assert that our veteran's termination pay doesn't go above the legal cap.

        Validated against the calculator: https://www.offsettingsubsidy.gov.hk/en/calculator.html
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        result = {
            'TERMINATION_PAYMENT_PRE_TRANSITION': 379931.51,
            'TERMINATION_PAYMENT_POST_TRANSITION': 10068.49,
            'TERMINATION_PAYMENT': 390000.00,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    def test_termination_payment_manual_adjustment(self):
        """
        Ensure that a manual input correctly affect the result of the termination payment rules.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        last_payslip._set_input_values({
            'TERMINATION_PAYMENT_PRE_TRANSITION': 375000.00,
            'TERMINATION_PAYMENT_POST_TRANSITION': 25000.00,
        })
        last_payslip.compute_sheet()  # As this changes the outcome of the already computed lines, recomputation is needed.
        # In practice this setup is wrong, as pre+post is above 390k. Here, we just make sure that we protect the final payout
        # from being illegally over the cap even if manual overrides would trigger it.
        result = {
            'TERMINATION_PAYMENT_PRE_TRANSITION': 375000.00,
            'TERMINATION_PAYMENT_POST_TRANSITION': 25000.00,
            'TERMINATION_PAYMENT': 390000.00,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    def test_severance_payment_labels(self):
        """
        Assert that the label for termination payment is set correctly if the termination reason warrants a severance payment.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        termination_pay_lines = last_payslip.line_ids.filtered(
            lambda line: line.code in ('TERMINATION_PAYMENT_PRE_TRANSITION', 'TERMINATION_PAYMENT_POST_TRANSITION', 'TERMINATION_PAYMENT')
        ).sorted('sequence')
        self.assertRecordValues(
            termination_pay_lines,
            [{
                'name': 'Severance Payment - Pre-Transition'
            }, {
                'name': 'Severance Payment - Post-Transition'
            }, {
                'name': 'Severance Payment'
            }]
        )

    def test_long_service_payment_labels(self):
        """
        Assert that the label for termination payment is set correctly if the termination reason warrants a long service payment.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='hr.departure_retired',
        )
        termination_pay_lines = last_payslip.line_ids.filtered(
            lambda line: line.code in ('TERMINATION_PAYMENT_PRE_TRANSITION', 'TERMINATION_PAYMENT_POST_TRANSITION', 'TERMINATION_PAYMENT')
        ).sorted('sequence')
        self.assertRecordValues(
            termination_pay_lines,
            [{
                'name': 'Long Service Payment - Pre-Transition'
            }, {
                'name': 'Long Service Payment - Post-Transition'
            }, {
                'name': 'Long Service Payment'
            }]
        )

    def test_termination_payment_offset(self):
        """
        Ensure that the offsets are correctly inputted and affecting the net.
        Compares the net without and with offset to avoid the calculation test failing for unrelated reasons.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        base_net = last_payslip.line_ids.filtered(lambda line: line.code == 'NET').total

        last_payslip._set_input_values({
            'TERMINATION_PAYMENT_PRE_TRANSITION_OFFSET': 100000.00,
            'TERMINATION_PAYMENT_POST_TRANSITION_OFFSET': 1000.00,
        })
        result = {
            'TERMINATION_PAYMENT_PRE_TRANSITION': 379931.51,
            'TERMINATION_PAYMENT_POST_TRANSITION': 10068.49,
            'TERMINATION_PAYMENT': 390000.00,
            'TERMINATION_PAYMENT_PRE_TRANSITION_OFFSET': -100000.00,
            'TERMINATION_PAYMENT_POST_TRANSITION_OFFSET': -1000.00,
            'NET': base_net - 101000,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

        # The offsets are funded by the MPF contributions, only the remainder costs the employer.
        # The added 6000 are the employer contributions, which are removed from the net but counted as cost.
        self.assertEqual(last_payslip.employer_cost, base_net - 101000 + 6000)

    def test_termination_payment_ineligibility(self):
        """ Make sure that an employee that is not meeting the years of service doesn't receive the special pays. """
        # The mid_timer isn't eligible for long service pay.
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.mid_timer,
            termination_reason='hr.departure_retired',
        )
        self.assertFalse(last_payslip.line_ids.filtered(lambda line: line.code == 'TERMINATION_PAYMENT'))

        # The rookie isn't eligible for both severance and long service pay.
        for termination_reason in ('hr.departure_retired', 'l10n_hk_hr_payroll.hr_departure_reason_redundancy'):
            with self.subTest(name=f"test_rookie_not_elligible_{termination_reason}"):
                last_payslip = self._setup_termination_and_last_payslip(
                    employee=self.rookie,
                    termination_reason=termination_reason,
                )
                self.assertFalse(last_payslip.line_ids.filtered(lambda line: line.code == 'TERMINATION_PAYMENT'))
        # Resigning makes you ineligible to termination pay.
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='hr.departure_resigned',
        )
        self.assertFalse(last_payslip.line_ids.filtered(lambda line: line.code == 'TERMINATION_PAYMENT'))

    def test_termination_payment_uncapped_wage(self):
        """
        Test that a monthly wage under the HK$ 22,500 threshold calculates correctly
        without being artificially capped to the maximum allowance.

        Validated against the calculator: https://www.offsettingsubsidy.gov.hk/en/calculator.html
        """
        # We are using a patch as this test would require regenerating the payslips; so it's faster this way.
        with patch.object(self.env.registry['hr.payslip'], '_get_713_gross_at_date', return_value=15000.0):
            last_payslip = self._setup_termination_and_last_payslip(
                employee=self.mid_timer,
                termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
            )

            result = {
                'TERMINATION_PAYMENT_POST_TRANSITION': 35863.01,
                'TERMINATION_PAYMENT': 35863.01,
            }
            self._validate_payslip(last_payslip, result, skip_lines=True)

    def test_termination_payment_hourly_wage(self):
        """
        Test that hourly wage employees correctly use the 18-days calculation method.

        Validated against the calculator: https://www.offsettingsubsidy.gov.hk/en/calculator.html
        """
        self.mid_timer.write({
            'wage_type': 'hourly',
            'hourly_wage': 100.0,
        })
        self.mid_timer.resource_calendar_id.hours_per_day = 8.0

        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.mid_timer,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        result = {
            'TERMINATION_PAYMENT_POST_TRANSITION': 51642.74,
            'TERMINATION_PAYMENT': 51642.74,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    ###########################
    # Payment in Lieu of notice
    ###########################

    def test_payment_in_lieu_of_notice(self):
        """
        Test adding a payment in lieu of notice in the last payslip of an employee.
        Asserts that the amount of the input is represented in the total, and the quantity of the line.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        base_net = last_payslip.line_ids.filtered(lambda line: line.code == 'NET').total
        last_payslip._set_input_value('PAYMENT_IN_LIEU_OF_NOTICE', 2)  # 2 months
        # A clean 60000 every month in the last 12 payslips; so the result is simply 60000*2
        result = {
            'PAYMENT_IN_LIEU_OF_NOTICE': 120000.00,
            'NET': base_net + 120000.00,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)
        pil_line = last_payslip.line_ids.filtered(lambda line: line.code == 'PAYMENT_IN_LIEU_OF_NOTICE')
        self.assertEqual(pil_line.quantity, 2)

    def test_payment_in_lieu_of_notice_daily(self):
        """
        Test adding a payment in lieu of notice (daily) in the last payslip of an employee.
        Asserts that the amount of the input is represented in the total, and the quantity of the line.

        12-months average daily wage validated with https://www.labour.gov.hk/eng/labour/avgMonthSalaryCalculator.htm
        """
        self.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_payment_in_lieu_of_notice').active = False
        self.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_payment_in_lieu_of_notice_weekly').active = True
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        last_payslip._set_input_value('PAYMENT_IN_LIEU_OF_NOTICE_WEEKLY', 21)  # 3 weeks
        # 12-Month Average Daily Wages: $ 1,972.60
        result = {
            'PAYMENT_IN_LIEU_OF_NOTICE_WEEKLY': 41424.6,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)
        pil_line = last_payslip.line_ids.filtered(lambda line: line.code == 'PAYMENT_IN_LIEU_OF_NOTICE_WEEKLY')
        self.assertEqual(pil_line.quantity, 21)

    def test_payment_in_lieu_of_notice_custom_ams(self):
        """
        Test adding a payment in lieu of notice and set the CUST_AVG_MONTHLY_SALARY to test the result.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        last_payslip._set_input_values({
            'PAYMENT_IN_LIEU_OF_NOTICE': 2,
            'CUST_AVG_MONTHLY_SALARY': 50000,
        })
        result = {
            'PAYMENT_IN_LIEU_OF_NOTICE': 100000.00,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    def test_payment_in_lieu_of_notice_incomplete_year(self):
        """
        Test adding a payment in lieu of notice in the last payslip of an employee who did not work for a full year.
        This employee's contract started in the middle of a month.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.rookie,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        last_payslip._set_input_value('PAYMENT_IN_LIEU_OF_NOTICE', 1)  # 1 month
        # 18000 * 9, with a first month at 9870.67
        result = {
            'PAYMENT_IN_LIEU_OF_NOTICE': 18047.21,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    def test_payment_in_lieu_of_notice_with_leaves_and_commission(self):
        """
        Test adding a payment in lieu of notice in the last payslip of an employee; when they had leaves (unpaid and
        not fully paid) in the last 12 months.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.mid_timer,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        last_payslip._set_input_value('PAYMENT_IN_LIEU_OF_NOTICE', 2)
        result = {
            'PAYMENT_IN_LIEU_OF_NOTICE': 65561.46,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    #####################
    # End Of Year Payment
    #####################

    def test_end_of_year_payment(self):
        """
        Test that the end of year payment is automatically added in December, which is the default EOY pay month.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        # As the wage is a clean 60000 each month and there has been no leaves, the rate will be 100% of 60000 (the AMS)
        result = {
            'END_OF_YEAR_PAYMENT': 60000.0,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)
        pil_line = last_payslip.line_ids.filtered(lambda line: line.code == 'END_OF_YEAR_PAYMENT')
        self.assertEqual(pil_line.rate, 100)

    def test_end_of_year_payment_company_setting(self):
        """
        Test changing the EOY pay month in the company setting and ensuring the payment is automatically added.
        """
        nov_payslip = self.veteran.slip_ids[0]
        self.assertFalse(nov_payslip.line_ids.filtered(lambda line: line.code == 'END_OF_YEAR_PAYMENT'))
        self.env.company.l10n_hk_eoy_pay_month = '11'
        nov_payslip.action_payslip_draft()
        nov_payslip.action_refresh_from_work_entries()
        result = {
            'END_OF_YEAR_PAYMENT': 54904.11,
        }
        self._validate_payslip(nov_payslip, result, skip_lines=True)

    def test_end_of_year_payment_manual_trigger(self):
        """
        Test that the end of year payment is correctly added when the input is set.
        """
        nov_payslip = self.veteran.slip_ids[0]
        self.assertFalse(nov_payslip.line_ids.filtered(lambda line: line.code == 'END_OF_YEAR_PAYMENT'))

        nov_payslip.action_payslip_draft()
        nov_payslip._set_input_value('END_OF_YEAR_PAYMENT', 10000.00)

        result = {
            'END_OF_YEAR_PAYMENT': 10000.00,
        }
        self._validate_payslip(nov_payslip, result, skip_lines=True)
        self.assertEqual(self.env.company.l10n_hk_eoy_pay_month, '12')  # The month is still December

    def test_end_of_year_payment_proration(self):
        """
        Test that the end of year payment is properly prorated based on the work days in the year.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.rookie,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        # 0 outside the EOY month to enable the automatic calculation
        rule = last_payslip.struct_id.rule_ids.filtered(lambda r: r.code == 'END_OF_YEAR_PAYMENT')[:1]
        last_payslip.update({
            'input_line_ids': [Command.create({'name': rule.input_name, 'salary_rule_id': rule.id, 'amount': 0})],
        })
        result = {
            'END_OF_YEAR_PAYMENT': 14357.33,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)
        pil_line = last_payslip.line_ids.filtered(lambda line: line.code == 'END_OF_YEAR_PAYMENT')
        self.assertAlmostEqual(pil_line.rate, 79.45, delta=0.01)

    def test_disabling_end_of_year_payment(self):
        """
        Ensure that the automatic end of year payment can be set to 0 manually if triggered due to the month set in the setting.
        """
        last_payslip = self._setup_termination_and_last_payslip(
            employee=self.veteran,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )
        # Add the input with an amount of 0
        rule = last_payslip.struct_id.rule_ids.filtered(lambda r: r.code == 'END_OF_YEAR_PAYMENT')[:1]
        last_payslip.update({
            'input_line_ids': [Command.create({'name': rule.input_name, 'salary_rule_id': rule.id, 'amount': 0})],
        })
        result = {
            'END_OF_YEAR_PAYMENT': 0.00,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)

    #############
    # Other tests
    #############

    def test_new_hire_zero_history_no_crash(self):
        """
        Test that statutory rules (PILON and End of Year Payment) do not crash
        when an employee is terminated in their very first month with absolutely no prior payslips.
        """
        absolute_rookie = self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2026, 12, 1),
                'contract_date_start': date(2026, 12, 1),
                'contract_date_end': date(2026, 12, 15),
                'wage': 20000.0,
                'l10n_hk_member_class_id': self.member_class.id,
            },
            employee_fields={'name': 'Absolute Rookie'}
        )

        last_payslip = self._setup_termination_and_last_payslip(
            employee=absolute_rookie,
            termination_reason='l10n_hk_hr_payroll.hr_departure_reason_redundancy',
        )

        # Trigger PILON for 1 month
        last_payslip._set_input_value('PAYMENT_IN_LIEU_OF_NOTICE', 1)

        # Because there is no history, the automated 12-month average calculations
        # should gracefully fall back to 0.0 without throwing exceptions.
        result = {
            'PAYMENT_IN_LIEU_OF_NOTICE': 0.0,
            'END_OF_YEAR_PAYMENT': 0.0,
        }
        self._validate_payslip(last_payslip, result, skip_lines=True)
