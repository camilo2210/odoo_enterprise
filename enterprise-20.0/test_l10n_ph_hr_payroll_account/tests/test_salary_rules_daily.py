# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.addons.test_l10n_ph_hr_payroll_account.tests.common import TestL10NPhHrPayrollCommon

from odoo.tests.common import tagged


@tagged("post_install", "post_install_l10n", "-at_install", "payslips_validation")
class TestPayslipValidationDaily(TestL10NPhHrPayrollCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.average_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2023, 1, 1),
                'contract_date_start': date(2023, 1, 1),
                'l10n_ph_hr_payroll_daily_wage': 1200.0,
                'schedule_pay': 'semi-monthly',
                'wage_type': 'daily',
                'l10n_ph_hr_payroll_employee_rank': 'rank_and_file',
            },
        )
        cls.high_earner_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2021, 1, 1),
                'contract_date_start': date(2021, 1, 1),
                'l10n_ph_hr_payroll_daily_wage': 5000.0,
                'schedule_pay': 'semi-monthly',
                'wage_type': 'daily',
                'l10n_ph_hr_payroll_employee_rank': 'managerial',
            },
        )
        cls.minimum_wage_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2026, 1, 1),
                'contract_date_start': date(2026, 1, 1),
                'l10n_ph_hr_payroll_daily_wage': 645.0,
                'schedule_pay': 'semi-monthly',
                'wage_type': 'daily',
                'l10n_ph_hr_payroll_minimum_wage_earner': True,
            },
        )

    def test_daily_average_wage_employee_payslip(self):
        """ Test the amounts of the payslip of an employee with an average wage. """
        self._set_test_employee(self.average_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        # 1200 daily => 1200 * 261 / (261 * 8) => 150 hourly
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 13200.0),
        })

        payslip_results = {
            'BASIC': 13200.0,
            'OB': 0.0,
            'SSS_CONTRIB': -662.5,
            'PHILHEALTH_CONTRIB': -326.25,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 12_111.25,
            'WITHH_TAX': -254.14,
            'NET': 11_857.11,
            'SSS_ER_CONTRIB': 1325.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 326.25,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1100.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_minimum_wage_employee_payslip(self):
        """ Test the amounts of the payslip of an employee that is a minimum wage earner. """
        self._set_test_employee(self.minimum_wage_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        # 645 daily => 645 * 261 / (261 * 8) => 80.625 hourly
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 7095.0),
        })

        payslip_results = {
            'BASIC': 7095.0,
            'OB': 0.0,
            'SSS_CONTRIB': -350.0,
            'PHILHEALTH_CONTRIB': -175.36,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 0.0,
            'WITHH_TAX': 0.0,
            'NET': 6469.64,
            'SSS_ER_CONTRIB': 700.0,
            'SSS_EC_CONTRIB': 5.0,
            'PHILHEALTH_ER_CONTRIB': 175.36,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 591.25,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_minimum_wage_employee_payslip_tax(self):
        """
        Test the amounts of the payslip of an employee that is a minimum wage earner.
        A minimum wage earner is tax-exempt for their basic wage, and only other benefits or commissions are taxable.
        """
        self._set_test_employee(self.minimum_wage_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        # Add a cash allowance; which will be taxed if it goes above the 90k tax-free limit.
        payslip._set_input_value('CA', 110_000)
        payslip.compute_sheet()
        payslip.action_validate()
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 7095.0),
        })

        payslip_results = {
            'BASIC': 7095.0,
            'CA': 110000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -175.36,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 108_849.64,
            'WITHH_TAX': -24_425.69,
            'NET': 91_518.95,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 175.36,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 591.25,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_high_wage_employee_payslip(self):
        """ Test the amounts of the payslip of an employee with a high wage. """
        self._set_test_employee(self.high_earner_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        # 5000 daily => 5000 * 261 / (261 * 8) => 625 hourly
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 55_000.0),
        })

        payslip_results = {
            'BASIC': 55_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -1250.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 52_775.0,
            'WITHH_TAX': -9131.2,
            'NET': 43_643.8,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 1250.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 4583.33,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_average_wage_employee_payslip_tardiness(self):
        """ Test the result of an employee receiving a tardiness penalty. """
        self._set_test_employee(self.average_employee)
        self._make_work_entry('l10n_ph_hr_payroll_tardiness', date(2026, 1, 5), 8, 10)

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        # 1200 daily => 1200 * 261 / (261 * 8) => 150 hourly
        # Unlike monthly paid employees, for daily paid the same rate is used for both lines.
        self._validate_worked_days(payslip, {
            'TARD': (0.25, 2.0, -300.0),
            '002.00': (11.0, 88.0, 13200.0),
        })

        payslip_results = {
            'BASIC': 13_200.0,
            'TARD': -300.0,
            'OB': 0.0,
            'SSS_CONTRIB': -662.5,
            'PHILHEALTH_CONTRIB': -326.25,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 11_811.25,
            'WITHH_TAX': -209.14,
            'NET': 11_602.11,
            'SSS_ER_CONTRIB': 1325.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 326.25,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1075.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_worked_day_differential_regular_holiday(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a holiday. """
        self._set_test_employee(self.average_employee)
        self._set_night_shift()
        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 2))
        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 6), date(2026, 1, 7))

        # Attendance
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 2), 8, 12)
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 2), 13, 17)
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 7), 8, 12)
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 7), 13, 17)
        # Overtime
        self._make_work_entry('l10n_ph_hr_payroll_overtime', date(2026, 1, 2), 17, 19)
        # Night Shift
        self._make_work_entry('l10n_ph_hr_payroll_ns', date(2026, 1, 6), 21, 24)
        self._make_work_entry('l10n_ph_hr_payroll_ns', date(2026, 1, 7), 1, 6)
        # Night Shift - Overtime
        self._make_work_entry('l10n_ph_hr_payroll_ns_overtime', date(2026, 1, 7), 6, 7)

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        # 1200 daily => 1200 * 261 / (261 * 8) => 150 hourly
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_RH': (0.125, 1.0, 429.0),  # 150 * 2.86 => 429
            'OVERTIME_RH': (0.25, 2.0, 780.0),  # 150 * 2 * 2.60 => 780
            'WORK100_NS': (1.0, 8.0, 1320.0),  # 150 * 8 * 1.10 => 1320
            'WORK100_NS_RH': (1.0, 8.0, 2640.0),  # 150 * 8 * 2.20 => 2640
            'WORK100_RH': (2.0, 16.0, 4800.0),  # 150 * 16 * 2 => 4800
            '002.00': (7.0, 56.0, 8400.0),  # 150 * 56 => 8400
        })
        payslip_results = {
            'BASIC': 13200.0,
            'HP': 4050.0,
            'OP': 720.0,
            'NSD': 399.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -326.25,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 17_067.75,
            'WITHH_TAX': -1_017.65,
            'NET': 16_050.1,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 326.25,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1100.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_regular_holiday(self):
        """ Test the wages of an employee with a regular holiday. """
        self._set_test_employee(self.average_employee)

        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 2))
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))

        # 1200 daily => 1200 * 261 / (261 * 8) => 150 hourly
        self._validate_worked_days(payslip, {
            'RH_LEAVE': (1.0, 8.0, 1200.0),  # 150 * 8 => 1200
            '002.00': (10.0, 80.0, 12_000.0),  # 150 * 80 => 12_000
        })
        payslip_results = {
            'BASIC': 12_000.0,
            'HP': 1200.0,
            'OB': 0.0,
            'SSS_CONTRIB': -662.5,
            'PHILHEALTH_CONTRIB': -326.25,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 12_111.25,
            'WITHH_TAX': -254.14,
            'NET': 11_857.11,
            'SSS_ER_CONTRIB': 1325.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 326.25,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1000.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_worked_day_differential_special_non_working_holiday_rest_day(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a special non-working holiday on a rest day. """
        self._set_test_employee(self.average_employee)
        self._make_holiday('l10n_ph_hr_payroll_snwh_leave', date(2026, 1, 3))
        self._make_holiday('l10n_ph_hr_payroll_snwh_leave', date(2026, 1, 10), date(2026, 1, 11))

        # Attendance
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 3), 8, 12)
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 3), 13, 17)
        # Overtime
        self._make_work_entry('l10n_ph_hr_payroll_overtime', date(2026, 1, 3), 17, 19)
        # Night Shift
        self._make_work_entry('l10n_ph_hr_payroll_ns', date(2026, 1, 10), 21, 24)
        self._make_work_entry('l10n_ph_hr_payroll_ns', date(2026, 1, 11), 1, 6)
        # Night Shift - Overtime
        self._make_work_entry('l10n_ph_hr_payroll_ns_overtime', date(2026, 1, 11), 6, 7)

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        # 1200 daily => 1200 * 261 / (261 * 8) => 150 hourly
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_SNW_REST': (0.125, 1.0, 321.75),  # 150 * 2.145 => 321.75
            'OVERTIME_SNW_REST': (0.25, 2.0, 585),  # 150 * 2 * 1.95 => 585
            'WORK100_NS_SNW_REST': (1.0, 8.0, 1980),  # 150 * 8 * 1.65 => 1980
            'WORK100_SNW_REST': (1.0, 8.0, 1800),  # 150 * 8 * 1.50 => 1800
            '002.00': (11.0, 88.0, 13_200),  # 150 * 88 => 13_200
        })
        payslip_results = {
            'BASIC': 13_200.0,
            'HP': 1425.0,
            'OP': 3052.5,
            'NSD': 209.25,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -326.25,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 16585.5,
            'WITHH_TAX': -925.28,
            'NET': 15_660.23,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 326.25,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1100.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_daily_worked_day_special_non_working_holiday_unworked(self):
        """ Test a daily employee who did not work on a SNW holiday. """
        self._set_test_employee(self.average_employee)
        self._make_holiday('l10n_ph_hr_payroll_snwh_leave', date(2026, 1, 7))
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        # 1200 daily => 1200 * 261 / (261 * 8) => 150 hourly
        self._validate_worked_days(payslip, {
            'SNWH_LEAVE': (1.0, 8.0, 0.0),
            '002.00': (10.0, 80.0, 12_000.0),  # 150 * 80 => 12_000
        })
        payslip_results = {
            'BASIC': 12_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -600.0,
            'PHILHEALTH_CONTRIB': -326.25,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 10_973.75,
            'WITHH_TAX': -83.51,
            'NET': 10_890.24,
            'SSS_ER_CONTRIB': 1200.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 326.25,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1000.0,
        }
        self._validate_payslip(payslip, payslip_results)
