# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.addons.test_l10n_ph_hr_payroll_account.tests.common import TestL10NPhHrPayrollCommon

from odoo.tests.common import tagged
from dateutil.rrule import rrule, MONTHLY
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time


@tagged("post_install", "post_install_l10n", "-at_install", "payslips_validation")
class TestPayslipValidation(TestL10NPhHrPayrollCommon):

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
                'wage': 15000.0,
                'schedule_pay': 'semi-monthly',
                'l10n_ph_hr_payroll_employee_rank': 'rank_and_file',
                'work_location_id': cls.work_location.id,
            },
        )
        cls.high_earner_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2021, 1, 1),
                'contract_date_start': date(2021, 1, 1),
                'wage': 75000.0,
                'schedule_pay': 'semi-monthly',
                'l10n_ph_hr_payroll_employee_rank': 'managerial',
                'work_location_id': cls.work_location.id,
            },
        )
        cls.minimum_wage_employee = cls._setup_employee(
            country=cls.country,
            structure_type=cls.structure_type,
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2026, 1, 1),
                'contract_date_start': date(2026, 1, 1),
                'wage': 7000.0,
                'schedule_pay': 'semi-monthly',
                'l10n_ph_hr_payroll_minimum_wage_earner': True,
                'work_location_id': cls.work_location.id,
            },
        )

    def test_average_wage_employee_payslip(self):
        """ Test the amounts of the payslip of an employee with an average wage. """
        self._set_test_employee(self.average_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 15000.0),
        })

        payslip_results = {
            'BASIC': 15000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13775.0,
            'WITHH_TAX': -503.7,
            'NET': 13271.3,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_minimum_wage_employee_payslip(self):
        """ Test the amounts of the payslip of an employee that is a minimum wage earner. """
        self._set_test_employee(self.minimum_wage_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 7000.0),
        })

        payslip_results = {
            'BASIC': 7000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -350.0,
            'PHILHEALTH_CONTRIB': -175.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 0.0,
            'WITHH_TAX': 0.0,
            'NET': 6375.0,
            'SSS_ER_CONTRIB': 700.0,
            'SSS_EC_CONTRIB': 5.0,
            'PHILHEALTH_ER_CONTRIB': 175.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 583.33,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_minimum_wage_employee_payslip_tax(self):
        """
        Test the amounts of the payslip of an employee that is a minimum wage earner.
        A minimum wage earner is tax-exempt for their basic wage, and only other benefits or commissions are taxable.
        """
        self.minimum_wage_employee.wage = 7_000
        self._set_test_employee(self.minimum_wage_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        # Add a cash allowance; which will be taxed if it goes above the 90k tax-free limit.
        payslip._set_input_value('CA', 110_000)
        payslip.compute_sheet()
        payslip.action_validate()
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 7000.0),
        })

        payslip_results = {
            'BASIC': 7_000.0,
            'CA': 110000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -175.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 108_850.0,
            'WITHH_TAX': -24_425.8,
            'NET': 91_424.2,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 175.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 583.33,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_high_wage_employee_payslip(self):
        """ Test the amounts of the payslip of an employee with a high wage. """
        self._set_test_employee(self.high_earner_employee)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 75000.0),
        })

        payslip_results = {
            'BASIC': 75_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -1250.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 72_775.0,
            'WITHH_TAX': -14_131.2,
            'NET': 58_643.8,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 1250.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 6250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_average_wage_employee_payslip_tardiness(self):
        """ Test the result of an employee receiving a tardiness penalty. """
        self._set_test_employee(self.average_employee)
        self._make_work_entry('l10n_ph_hr_payroll_tardiness', date(2026, 1, 5), 8, 10)

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()
        self._validate_worked_days(payslip, {
            'TARD': (0.25, 2.0, -246.58),
            '002.00': (11.0, 88.0, 15000.0),
        })

        payslip_results = {
            'BASIC': 15000.0,
            'TARD': -246.58,
            'OB': 0.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_528.42,
            'WITHH_TAX': -466.71,
            'NET': 13_061.71,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1229.45,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_regular_day(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a regular day. """
        self._set_test_employee(self.average_employee)
        self._set_night_shift()
        self._make_work_entry('l10n_ph_hr_payroll_overtime', date(2026, 1, 5), 17, 19)
        self._make_work_entry('l10n_ph_hr_payroll_ns_overtime', date(2026, 1, 7), 6, 7)

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        self._validate_worked_days(payslip, {
            'OVERTIME_NS': (0.125, 1.0, 169.52),
            '040.00': (0.25, 2.0, 308.22),
            'WORK100_NS': (2.0, 16.0, 2924.53),
            '002.00': (9.0, 72.0, 12_272.73),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'OP': 462.33,
            'NSD': 212.67,
            'OB': 0.0,
            'SSS_CONTRIB': -787.5,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 14_412.5,
            'WITHH_TAX': -599.33,
            'NET': 13_813.18,
            'SSS_ER_CONTRIB': 1575.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_rest_day(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a rest day. """
        self._set_test_employee(self.average_employee)
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
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_REST': (0.125, 1.0, 229.19),
            'OVERTIME_REST': (0.25, 2.0, 416.71),
            'WORK100_NS_REST': (1.0, 8.0, 424.11),
            'WORK100_REST': (1.0, 8.0, 295.89),
            '002.00': (11.0, 88.0, 15_000.0),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'HP': 702.74,
            'OP': 514.11,
            'NSD': 149.06,
            'OB': 0.0,
            'SSS_CONTRIB': -812.5,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 15_078.41,
            'WITHH_TAX': -699.21,
            'NET': 14_379.2,
            'SSS_ER_CONTRIB': 1625.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_special_non_working_holiday(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a special non-working holiday. """
        self._set_test_employee(self.average_employee)
        self._set_night_shift()
        self._make_holiday('l10n_ph_hr_payroll_snwh_leave', date(2026, 1, 2))
        self._make_holiday('l10n_ph_hr_payroll_snwh_leave', date(2026, 1, 6), date(2026, 1, 7))

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
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_SNW': (0.125, 1.0, 229.19),
            'OVERTIME_SNW': (0.25, 2.0, 416.71),
            'WORK100_NS_SNW': (1.0, 8.0, 1787.75),
            'WORK100_SNW': (2.0, 16.0, 3319.05),
            'WORK100_NS': (1.0, 8.0, 1462.27),
            '002.00': (7.0, 56.0, 9545.45),
        })
        payslip_results = {
            'BASIC': 15_000.00,
            'HP': 998.63,
            'OP': 514.11,
            'NSD': 247.69,
            'OB': 0.0,
            'SSS_CONTRIB': -837.5,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 15_447.93,
            'WITHH_TAX': -754.64,
            'NET': 14_693.29,
            'SSS_ER_CONTRIB': 1675.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_special_non_working_holiday_rest_day(self):
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
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_SNW_REST': (0.125, 1.0, 264.45),
            'OVERTIME_SNW_REST': (0.25, 2.0, 480.82),
            'WORK100_NS_SNW_REST': (1.0, 8.0, 641.1),
            'WORK100_SNW_REST': (1.0, 8.0, 493.15),
            '002.00': (11.0, 88.0, 15_000.0),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'HP': 1171.23,
            'OP': 536.3,
            'NSD': 171.99,
            'OB': 0.0,
            'SSS_CONTRIB': -850.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 15_554.52,
            'WITHH_TAX': -770.63,
            'NET': 14_783.89,
            'SSS_ER_CONTRIB': 1700.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_special_non_working_holiday_unworked(self):
        """ Test an employee who did not work on a SNW holiday. """
        self._set_test_employee(self.average_employee)
        self._make_holiday('l10n_ph_hr_payroll_snwh_leave', date(2026, 1, 7))
        self._make_holiday('l10n_ph_hr_payroll_snwh_leave', date(2026, 1, 9))
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        self._validate_worked_days(payslip, {
            'SNWH_LEAVE': (2.0, 16.0, 2727.27),
            '002.00': (9.0, 72.0, 12272.73),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'NET': 13_271.3,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_regular_holiday(self):
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
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_RH': (0.125, 1.0, 352.6),
            'OVERTIME_RH': (0.25, 2.0, 641.1),
            'WORK100_NS': (1.0, 8.0, 1462.27),
            'WORK100_NS_RH': (1.0, 8.0, 2547.2),
            'WORK100_RH': (2.0, 16.0, 4699.87),
            '002.00': (7.0, 56.0, 9545.45),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'HP': 3328.77,
            'OP': 591.78,
            'NSD': 327.94,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 17_898.49,
            'WITHH_TAX': -1183.8,
            'NET': 16_714.69,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_regular_holiday_rest_day(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a holiday on a rest day. """
        self._set_test_employee(self.average_employee)
        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 3))
        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 10), date(2026, 1, 11))

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
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_RH_REST': (0.125, 1.0, 458.38),
            'OVERTIME_RH_REST': (0.25, 2.0, 833.42),
            'WORK100_NS_RH_REST': (1.0, 8.0, 1834.52),
            'WORK100_RH_REST': (1.0, 8.0, 1578.08),
            '002.00': (11.0, 88.0, 15_000.0),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'HP': 3747.94,
            'OP': 658.35,
            'NSD': 298.11,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 18_354.4,
            'WITHH_TAX': -1274.98,
            'NET': 17_079.42,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_double_holiday(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a double holiday. """
        self._set_test_employee(self.average_employee)
        self._set_night_shift()
        self._make_holiday('l10n_ph_hr_payroll_dh_leave', date(2026, 1, 2))
        self._make_holiday('l10n_ph_hr_payroll_dh_leave', date(2026, 1, 6), date(2026, 1, 7))

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
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_DH': (0.125, 1.0, 528.9),
            'OVERTIME_DH': (0.25, 2.0, 961.64),
            'WORK100_NS': (1.0, 8.0, 1462.27),
            'WORK100_NS_DH': (1.0, 8.0, 3632.13),
            'WORK100_DH': (2.0, 16.0, 6672.48),
            '002.00': (7.0, 56.0, 9545.45),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'HP': 6657.54,
            'OP': 702.74,
            'NSD': 442.6,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 21_452.88,
            'WITHH_TAX': -1894.68,
            'NET': 19_558.2,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_double_holiday_rest_day(self):
        """ Test the wage of an employee paid for a night shift, an overtime, and an overtime night shift on a double holiday on a rest day. """
        self._set_test_employee(self.average_employee)
        self._make_holiday('l10n_ph_hr_payroll_dh_leave', date(2026, 1, 3))
        self._make_holiday('l10n_ph_hr_payroll_dh_leave', date(2026, 1, 10), date(2026, 1, 11))

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
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_DH_REST': (0.125, 1.0, 687.58),
            'OVERTIME_DH_REST': (0.25, 2.0, 1250.14),
            'WORK100_NS_DH_REST': (1.0, 8.0, 3244.93),
            'WORK100_DH_REST': (1.0, 8.0, 2860.27),
            '002.00': (11.0, 88.0, 15_000.0),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'HP': 6793.14,
            'OP': 802.6,
            'NSD': 447.17,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 21_692.91,
            'WITHH_TAX': -1942.68,
            'NET': 19_750.23,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_regular_holiday(self):
        """ Test the wages of an employee with a regular holiday. """
        self._set_test_employee(self.average_employee)

        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 2))
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))

        self._validate_worked_days(payslip, {
            'RH_LEAVE': (1.0, 8.0, 1363.64),
            '002.00': (10.0, 80.0, 13_636.36),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'NET': 13_271.3,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_double_holiday(self):
        """ Test the wages of an employee with a double holiday. """
        self._set_test_employee(self.average_employee)

        self._make_holiday('l10n_ph_hr_payroll_dh_leave', date(2026, 1, 2))
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))

        self._validate_worked_days(payslip, {
            'DH_LEAVE': (1.0, 8.0, 2349.94),
            '002.00': (10.0, 80.0, 13_636.36),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'HP': 986.3,
            'OB': 0.0,
            'SSS_CONTRIB': -800.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 14_711.3,
            'WITHH_TAX': -644.15,
            'NET':  14_067.16,
            'SSS_ER_CONTRIB': 1600.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_weekend_holiday(self):
        """
        Ensure that holidays set on a weekend does not cound as worked day nor affect the payslip.
        This is a safety measure to ensure we don't cause issue with the special flows involving holidays and out of schedule work.
        """
        self._set_test_employee(self.average_employee)

        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 3))
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))

        self._validate_worked_days(payslip, {
            '002.00': (11.0, 88.0, 15_000.00),
        })
        payslip_results = {
            'BASIC': 15_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'NET': 13_271.3,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_manager_fringe_benefits(self):
        """ Ensure that a manager employee receiving fringe benefits will not be taxed on them; but the company will pay for it. """
        self._set_test_employee(self.high_earner_employee)

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip._set_input_value('CFB', 25_000)
        payslip._set_input_value('NCFB', 50_000)
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 75_000.0,
            'CFB': 25_000.0,
            'NCFB': 50_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -1250.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 72_775.0,
            'WITHH_TAX': -14_131.2,
            'NET': 83_643.8,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 1250.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 6250.0,
            'FBT': 40_384.62,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_supervisor_fringe_benefits(self):
        """ Ensure that a supervisor employee receiving fringe benefits will not be taxed on them; but the company will pay for it. """
        self._set_test_employee(self.high_earner_employee)
        self.high_earner_employee.l10n_ph_hr_payroll_employee_rank = 'supervisory'

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip._set_input_value('CFB', 25_000)
        payslip._set_input_value('NCFB', 50_000)
        payslip.compute_sheet()

        # Exact same as manager
        payslip_results = {
            'BASIC': 75_000.0,
            'CFB': 25_000.0,
            'NCFB': 50_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -1250.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 72_775.0,
            'WITHH_TAX': -14_131.2,
            'NET': 83_643.8,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 1250.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 6250.0,
            'FBT': 40_384.62,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_rank_and_file_fringe_benefits(self):
        """ Ensure that a rank and file employee receiving fringe benefits will not be taxed on them; but the company will pay for it. """
        self._set_test_employee(self.average_employee)

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip._set_input_value('CFB', 2500)
        payslip._set_input_value('NCFB', 5000)
        payslip.compute_sheet()

        # Exact same as manager
        payslip_results = {
            'BASIC': 15_000.0,
            'CFB': 2500.0,
            'NCFB': 5000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 21_275.0,
            'WITHH_TAX': -1859.1,
            'NET': 14415.9,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_rest_day_manager(self):
        """ Test the wage of a manager paid for a night shift, an overtime, and an overtime night shift on a rest day. """
        self._set_test_employee(self.high_earner_employee)
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
        # Managers are not entitled to pay (by default) for night shifts, or any other special shifts.
        # Can be configured in the system param; this asserts that we do pick the 0 rate as expected.
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_REST': (0.125, 1.0, 0.0),
            'OVERTIME_REST': (0.25, 2.0, 0.0),
            'WORK100_NS_REST': (1.0, 8.0, 0.0),
            'WORK100_REST': (1.0, 8.0, 0.0),
            '002.00': (11.0, 88.0, 75_000.0),
        })
        payslip_results = {
            'BASIC': 75_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -1250.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 72_775.0,
            'WITHH_TAX': -14131.2,
            'NET': 58_643.8,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 1250.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 6250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_worked_day_differential_rest_day_supervisor(self):
        """ Test the wage of a supervisor paid for a night shift, an overtime, and an overtime night shift on a rest day. """
        self._set_test_employee(self.high_earner_employee)
        self.high_earner_employee.l10n_ph_hr_payroll_employee_rank = 'supervisory'
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
        # Supervisors are also not entitled to pay (by default) for night shifts, or any other special shifts.
        # Can be configured in the system param; this asserts that we do pick the 0 rate as expected.
        self._validate_worked_days(payslip, {
            'OVERTIME_NS_REST': (0.125, 1.0, 0.0),
            'OVERTIME_REST': (0.25, 2.0, 0.0),
            'WORK100_NS_REST': (1.0, 8.0, 0.0),
            'WORK100_REST': (1.0, 8.0, 0.0),
            '002.00': (11.0, 88.0, 75_000.0),
        })
        payslip_results = {
            'BASIC': 75_000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -1250.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 72_775.0,
            'WITHH_TAX': -14131.2,
            'NET': 58_643.8,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 1250.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 6250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_de_minimis_caps_schedule(self):
        """ Test the different limits for de minimis rules. """
        self._set_test_employee(self.average_employee)
        test_data = [
            ('DM_RICE', 2500, 'monthly', 'employee'),
            ('DM_CLOTHING', 8000, 'annually', 'payslip'),
            ('DM_MED_CASH', 2000, 'semi-annually', 'payslip'),
        ]
        for dm_rule, cap, schedule, dm_type in test_data:
            with self.subTest(f"Testing De Minimis cap for schedule {schedule}"):
                rule_amount = int(cap * .6)
                # First slip always in Jan, that sets 60% of the cap.
                if dm_type == "employee":
                    self.average_employee.version_id._set_property_input_value(dm_rule, rule_amount)
                payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
                if dm_type == "payslip":
                    payslip._set_input_value(dm_rule, rule_amount)
                payslip.compute_sheet()
                payslip.action_payslip_done()
                self._validate_payslip(
                    payslip,
                    {
                        dm_rule: rule_amount,
                    },
                    skip_lines=True,
                )
                # Second payslip later in the month, goes over the cap
                payslip = self._generate_payslip(date(2026, 1, 16), date(2026, 1, 31))
                payslip._set_input_value(dm_rule, rule_amount) if dm_type == 'payslip' else {}
                payslip.compute_sheet()
                payslip.action_payslip_done()
                capped_amount = cap - rule_amount
                self._validate_payslip(
                    payslip,
                    {
                        dm_rule: capped_amount,
                        'DM_EXCESS': rule_amount - capped_amount,
                        'OB': rule_amount - capped_amount,
                    },
                    skip_lines=True,
                )
                # Last payslip is in a future period, after the cap has been reset.
                if schedule == 'monthly':
                    payslip = self._generate_payslip(date(2026, 2, 1), date(2026, 2, 15))
                elif schedule == 'semi-annually':
                    payslip = self._generate_payslip(date(2026, 7, 1), date(2026, 7, 15))
                else:
                    payslip = self._generate_payslip(date(2027, 1, 1), date(2027, 1, 15))
                payslip._set_input_value(dm_rule, rule_amount) if dm_type == 'payslip' else {}
                payslip.compute_sheet()
                self._validate_payslip(
                    payslip,
                    {
                        dm_rule: rule_amount,
                    },
                    skip_lines=True,
                )
                if dm_type == 'employee':
                    self.average_employee.version_id._set_property_input_value(dm_rule, 0)

    def test_de_minimis_daily_meal(self):
        """ Test that the daily meal cap at the minimum wage amount * 30%, and 'reset' daily. """
        self._set_test_employee(self.average_employee)
        # First day, try to go over the cap.
        self.average_employee.version_id._set_property_input_value('DM_DAILY_MEAL', 10000)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 1))
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self._validate_payslip(
            payslip,
            {
                'DM_DAILY_MEAL': 208.5,
            },
            skip_lines=True,
        )
        # Second day, should allow full amount again, this time we set below cap.
        self.average_employee.version_id._set_property_input_value('DM_DAILY_MEAL', 200)
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 1))
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self._validate_payslip(
            payslip,
            {
                'DM_DAILY_MEAL': 200.00,
            },
            skip_lines=True,
        )

    def test_de_minimis_leave_monetization(self):
        """ Test that the daily meal cap at the minimum wage amount * 30%, and 'reset' daily. """
        self._set_test_employee(self.average_employee)
        # First, use 10 leaves
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip._set_input_value('DM_LEAVE_MONETIZATION', 10)
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self._validate_payslip(
            payslip,
            {
                'DM_LEAVE_MONETIZATION': 9_863.01,  # Equivalent of 10 days of contract wages
            },
            skip_lines=True,
        )
        # Second use 10 again, but it caps at 2
        payslip = self._generate_payslip(date(2026, 1, 16), date(2026, 1, 31))
        payslip._set_input_value('DM_LEAVE_MONETIZATION', 10)
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self._validate_payslip(
            payslip,
            {
                'DM_LEAVE_MONETIZATION': 1972.6,
            },
            skip_lines=True,
        )
        # It resets next year
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip._set_input_value('DM_LEAVE_MONETIZATION', 10)
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self._validate_payslip(
            payslip,
            {
                'DM_LEAVE_MONETIZATION': 9_863.01,
            },
            skip_lines=True,
        )

    def test_other_benefit_cap(self):
        """
        Test a payslip where the other benefits gets over the cap and get into taxable benefits.
        We do so by giving de minimis over the cap.
        """
        self._set_test_employee(self.average_employee)
        self.average_employee.version_id._set_property_input_value('DM_RICE', 93_500)  # Doesn't make sense, just to test in a single payslip
        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.compute_sheet()
        payslip_results = {
            'BASIC': 15_000.0,
            'DM_RICE': 2500.0,
            'DM_EXCESS': 91_000.0,
            'OB': 90_000.0,
            'TOB': 1000.0,
            'SSS_CONTRIB': -800.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 14_725.0,
            'WITHH_TAX': -646.2,
            'NET': 106_578.8,
            'SSS_ER_CONTRIB': 1600.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_13th_month(self):
        """
        The provision amount is tested indirectly in the various tests above, so this one will just create one year
        of payslips, and ensure the 13th month is correct when enabled in december.
        """
        self._set_test_employee(self.average_employee)
        # create slips for the whole of 2026.
        date_start = date(2026, 1, 1)
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            # 2 payslips per month.
            for day_start, day_end in ((0, 15), (16, 31)):
                payslip = self._generate_payslip(dt.date() + relativedelta(day=day_start), dt.date() + relativedelta(day=day_end))
                payslip.action_validate()

        # Manually create december slips as we want to enable 13th month on the last one
        payslip = self._generate_payslip(date(2026, 12, 1), date(2026, 12, 15))
        payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 16), date(2026, 12, 31))
        payslip.l10n_ph_hr_payroll_includes_13th_month = True
        payslip.compute_sheet()
        payslip_results = {
            'BASIC': 15_000.0,
            'OB': 30_000.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': -1.2,
            'NET': 43_270.1,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 30_000.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_13th_month_twice(self):
        """ Ensure that if 13th month is paid twice (or more) in a year, it is correctly prorated. """
        self._set_test_employee(self.average_employee)
        # create slips for the whole of 2026.
        date_start = date(2026, 1, 1)
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            # 2 payslips per month.
            for day_start, day_end in ((0, 15), (16, 31)):
                payslip = self._generate_payslip(dt.date() + relativedelta(day=day_start), dt.date() + relativedelta(day=day_end))
                if day_start == 16 and dt.date().month == 6:  # Add 13th month in the middle of the year
                    payslip.l10n_ph_hr_payroll_includes_13th_month = True
                    payslip.compute_sheet()
                payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 1), date(2026, 12, 15))
        payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 16), date(2026, 12, 31))
        payslip.l10n_ph_hr_payroll_includes_13th_month = True
        payslip.compute_sheet()
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 15_000.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': -1.2,
            'NET': 28_270.1,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 15_000.0,  # Half of what it would be for a full year, as it was split in two
        })

    @freeze_time('2025-3-28')
    def test_separation_pay_full(self):
        """ Test and validate the calculation of a full separation pay. """
        self._set_test_employee(self.average_employee)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'departure_reason_id': self.env.ref('l10n_ph_hr_payroll.hr_departure_reason_automation_separated').id,
        }])
        payslip = self._generate_payslip(date(2025, 3, 16), date(2025, 3, 31))
        self.assertRecordValues(payslip, [{
            'l10n_ph_hr_payroll_is_final_slip': True,
            'l10n_ph_hr_payroll_includes_13th_month': True,
            'l10n_ph_hr_payroll_includes_tax_annualization': True,
            'l10n_ph_hr_payroll_includes_separation_pay': True,
        }])
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 1250.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': 503.7,
            'NET': 75_025.0,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 1250.0,
            'SEPARATION': 60_000.0,  # One month of wage per year of services.
        })

    @freeze_time('2025-3-28')
    def test_separation_pay_half(self):
        """ Test and validate the calculation of a half separation pay. """
        self._set_test_employee(self.average_employee)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'departure_reason_id': self.env.ref('l10n_ph_hr_payroll.hr_departure_reason_retrenchement').id,
        }])
        payslip = self._generate_payslip(date(2025, 3, 16), date(2025, 3, 31))
        self.assertRecordValues(payslip, [{
            'l10n_ph_hr_payroll_is_final_slip': True,
            'l10n_ph_hr_payroll_includes_13th_month': True,
            'l10n_ph_hr_payroll_includes_tax_annualization': True,
            'l10n_ph_hr_payroll_includes_separation_pay': True,
        }])
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 1250.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': 503.7,
            'NET': 45_025.0,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 1250.0,
            'SEPARATION': 30_000.0,  # Half a month of wage per year of services.
        })

    @freeze_time('2025-3-28')
    def test_retirement_pay(self):
        """ Test and validate the calculation of a full separation pay. """
        self._set_test_employee(self.average_employee)
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'departure_reason_id': self.env.ref('l10n_ph_hr_payroll.hr_departure_reason_mandatory_retirement').id,
        }])
        payslip = self._generate_payslip(date(2025, 3, 16), date(2025, 3, 31))
        self.assertRecordValues(payslip, [{
            'l10n_ph_hr_payroll_is_final_slip': True,
            'l10n_ph_hr_payroll_includes_13th_month': True,
            'l10n_ph_hr_payroll_includes_tax_annualization': True,
            'l10n_ph_hr_payroll_includes_retirement_pay': True,
        }])
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 1250.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': 503.7,
            'NET': 59_408.56,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 1250.0,
            'RETIREMENT': 44_383.56,
        })

    @freeze_time('2025-3-28')
    def test_retirement_leave_conversion(self):
        """ Test and validate the calculation of a retirement pay, with unused leaves to repay. """
        self._set_test_employee(self.average_employee)
        allocation = self.env["hr.leave.allocation"].create({
            "name": "Annual Leave Allocation",
            "work_entry_type_id": self.env.ref("hr_work_entry.ph_work_entry_type_legal_leave").id,
            "number_of_days": 10,
            "employee_id": self.employee.id,
            "state": "confirm",
            "date_from": "2025-01-01",
        })
        allocation.action_approve()
        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 31),
            'departure_reason_id': self.env.ref('l10n_ph_hr_payroll.hr_departure_reason_mandatory_retirement').id,
        }])
        payslip = self._generate_payslip(date(2025, 3, 16), date(2025, 3, 31))
        self.assertRecordValues(payslip, [{
            'l10n_ph_hr_payroll_is_final_slip': True,
            'l10n_ph_hr_payroll_includes_13th_month': True,
            'l10n_ph_hr_payroll_includes_tax_annualization': True,
            'l10n_ph_hr_payroll_includes_retirement_pay': True,
        }])
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 1250.0,
            'LEAVECON': 9863.01,
            'SSS_CONTRIB': -875.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 23_513.01,
            'WITHH_TAX': -2306.7,
            'TAX_ANNUALIZATION': 2306.7,
            'NET': 69_146.58,
            'SSS_ER_CONTRIB': 1750.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 1250.0,
            'RETIREMENT': 44_383.56,
        })

    def test_tax_annualization(self):
        """ Ensure that the tax annualization amount to a correct result. """
        self._set_test_employee(self.average_employee)
        # create slips for the whole of 2026.
        date_start = date(2026, 1, 1)
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            for day_start, day_end in ((0, 15), (16, 31)):
                payslip = self._generate_payslip(dt.date() + relativedelta(day=day_start), dt.date() + relativedelta(day=day_end))
                payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 1), date(2026, 12, 15))
        payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 16), date(2026, 12, 31))
        # Total withheld: 503.7 * 24 => 12088.8
        # Annualized total : 13775 * 24 => 330600 - 250000 (non-taxable part) => 80600 * 15% => 12090
        # We under withheld 1.2, which will be withheld during annualization
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 30_000.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': -1.2,
            'NET': 43_270.1,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 30_000.0,
        })

    def test_tax_annualization_prev_employee(self):
        """
        Ensure that the tax annualization amount to a correct result when a previous employer amounts.
        Are provided.
        """
        self._set_test_employee(self.average_employee)
        self.env['l10n_ph_hr_payroll.previous_employment'].create({
            "employee_id": self.average_employee.id,
            "version_ids": self.average_employee.version_id.ids,
            "tin": "987-654-321-000",
            "name": "Previous PH Corp",
            "address": "Cebu City",
            "zip": "6000",
            "taxable_salaries_other": 144000.0,
            "tax_withheld": 2849.4,
        })
        self.average_employee.write({
            'date_version': date(2026, 7, 1),
            'contract_date_start': date(2026, 7, 1),
        })
        # create slips for half the year. The first half, we assume the employee worked somewhere else.
        date_start = date(2026, 7, 1)
        for dt in rrule(MONTHLY, dtstart=date_start, until=date_start + relativedelta(month=11)):
            for day_start, day_end in ((0, 15), (16, 31)):
                payslip = self._generate_payslip(dt.date() + relativedelta(day=day_start), dt.date() + relativedelta(day=day_end))
                payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 1), date(2026, 12, 15))
        payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 16), date(2026, 12, 31))
        # Total withheld: 503.7 * 12 => 6044.4 + 2849.4 => 8893.8
        # Total Gross: 13775 * 12 => 165300 + 144000 => 309300
        # Annualized total : 309300 - 250000 (non-taxable part) => 59300 * 15% => 8895
        # We under withheld 1.2 (again), which will be withheld during annualization
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 15_000.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': -1.2,
            'NET': 28_270.1,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 15_000.0,
        })

    def test_tax_annualization_prev_employee_gap(self):
        """
        Ensure that the tax annualization amount to a correct result when a previous employer amounts.
        Are provided, but the employee had a out of work period causing the annualization to be 'big'
        """
        self._set_test_employee(self.average_employee)
        self.env['l10n_ph_hr_payroll.previous_employment'].create({
            "employee_id": self.average_employee.id,
            "version_ids": self.average_employee.version_id.ids,
            "tin": "987-654-321-000",
            "name": "Previous PH Corp",
            "address": "Cebu City",
            "zip": "6000",
            "taxable_salaries_other": 144000.0,
            "tax_withheld": 2849.4,
        })
        self.average_employee.write({
            'date_version': date(2026, 7, 1),
            'contract_date_start': date(2026, 7, 1),
        })
        # Only payslips for December
        payslip = self._generate_payslip(date(2026, 12, 1), date(2026, 12, 15))
        payslip.action_validate()
        payslip = self._generate_payslip(date(2026, 12, 16), date(2026, 12, 31))
        # Total withheld: 503.7 * 2 => 1007.4 + 2849.4 => 3856.8
        # Total Gross: 13775 * 2 => 27550 + 144000 => 171550
        # Annualized total : 171550 - 250000 (non-taxable part) => 0
        # We overwitheld, as the annual total is due is 0 but we only refund the part we paid ourselves.
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 2500.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13_775.0,
            'WITHH_TAX': -503.7,
            'TAX_ANNUALIZATION': 1007.4,
            'NET': 16_778.7,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            '13THMONTH': 2500.0,
        })

    def test_previous_employement_non_taxable_benefits(self):
        """
        Ensure that non-taxable benefits from a previous employment are counted for the cap before the benefits become
        taxable.
        """
        self._set_test_employee(self.average_employee)
        self.env['l10n_ph_hr_payroll.previous_employment'].create({
            "employee_id": self.average_employee.id,
            "version_ids": self.average_employee.version_id.ids,
            "tin": "987-654-321-000",
            "name": "Previous PH Corp",
            "address": "Cebu City",
            "zip": "6000",
            "nontax_13th_month": 80000.0,
        })
        self.average_employee.write({
            'date_version': date(2026, 7, 1),
            'contract_date_start': date(2026, 7, 1),
        })
        self.average_employee.version_id._set_property_input_value('DM_RICE', 13_500)
        payslip = self._generate_payslip(date(2026, 11, 16), date(2026, 11, 30))
        # 2500 (rice allowance) + 11 000 (excess) to add to the previous employment amount and go above the 90k cap
        payslip.compute_sheet()
        self._validate_payslip(payslip, {
            'BASIC': 15_000.0,
            'OB': 10000.0,
            'TOB': 1000.0,
            'SSS_CONTRIB': -800.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 14_725.0,
            'WITHH_TAX': -646.2,
            'NET': 26_578.8,
            'SSS_ER_CONTRIB': 1600.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
            'DM_RICE': 2500.0,
            'DM_EXCESS': 11_000.0,
        })

    def test_unpaid_leave_deduction(self):
        """
        Ensure that the amount deducted for unpaid leave is calculated using the EEMR, even for 'monthly paid' employees.
        """
        self._set_test_employee(self.average_employee)
        self._make_work_entry('l10n_ph_hr_payroll_unpaid_leave', date(2026, 11, 17), 8, 17)

        payslip = self._generate_payslip(date(2026, 11, 16), date(2026, 11, 30))
        payslip.compute_sheet()
        # Standard calculation would be: 15000 / (11 * 8) => 208.333333333 * 8 (unpaid hours) => 1363.64
        # EEMR calculation: (15000 * 24) / (8 * 365) => 123.29 * 8 => 986.301
        # Not using the EEMR would mean illegally reducing the wage of the employee /!\
        self._validate_worked_days(payslip, {
            '158.00': (1.0, 8.0, 0.0),
            '002.00': (10.0, 80.0, 14013.69),
        })

    def test_average_wage_employee_employer_cost(self):
        """ Test that employer_cost equal to categories['CASH_EARNINGS'] + categories['COMP'], plus the 13th month pay rule. """
        self._set_test_employee(self.average_employee)

        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2026, 1, 15),
            'departure_reason_id': self.env.ref('l10n_ph_hr_payroll.hr_departure_reason_automation_separated').id,
        }])
        self.average_employee.version_id._set_property_input_value("ECOLA", 200)
        self.average_employee.l10n_ph_hr_payroll_employee_rank = 'managerial'  # For the FBT

        self._make_holiday('l10n_ph_hr_payroll_rh_leave', date(2026, 1, 2))
        # Holiday Pay
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 2), 8, 12)
        self._make_work_entry('ph_work_entry_type_attendance', date(2026, 1, 2), 13, 17)
        # Overtime Pay
        self._make_work_entry('l10n_ph_hr_payroll_overtime', date(2026, 1, 2), 17, 19)
        # Night Shift Differential
        self._make_work_entry('l10n_ph_hr_payroll_ns', date(2026, 1, 2), 21, 24)
        # Tardiness
        self._make_work_entry('l10n_ph_hr_payroll_tardiness', date(2026, 1, 1), 8, 10)

        # Leave con
        allocation = self.env["hr.leave.allocation"].create({
            "name": "Annual Leave Allocation",
            "work_entry_type_id": self.env.ref("hr_work_entry.ph_work_entry_type_legal_leave").id,
            "number_of_days": 10,
            "employee_id": self.employee.id,
            "state": "confirm",
            "date_from": "2025-01-01",
        })
        allocation.action_approve()

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.l10n_ph_hr_payroll_includes_13th_month = True
        payslip._set_input_value('DM_RICE', 93_500)  # For DM_EXCESS
        payslip._set_input_value('CA', 25_000)
        payslip._set_input_value('CFB', 10_000)
        payslip._set_input_value('NCFB', 15_000)
        payslip.compute_sheet()
        payslip.action_validate()

        cash_earnings_category = self.env.ref('l10n_ph_hr_payroll.CASH_EARNINGS')
        comp_category = self.env.ref('hr_payroll.COMP')
        employer_cost_categories = self.env['hr.salary.rule.category'].search([
            ('id', 'child_of', (cash_earnings_category + comp_category).ids),
        ])
        employer_cost_lines = payslip.line_ids.filtered(
            lambda line: line.salary_rule_id.category_ids & employer_cost_categories or line.code == '13THMONTH'
        )

        self.assertEqual(payslip.employer_cost, sum(employer_cost_lines.mapped('total')))

    def test_loan_deductions_payslip(self):
        """ Test that loan repayments reduce the take home pay without reducing the taxable salary. """
        self._set_test_employee(self.average_employee)
        self.env['hr.salary.attachment'].create([
            {
                'employee_id': self.average_employee.id,
                'salary_rule_id': self.env.ref(f'l10n_ph_hr_payroll.{xml_id}').id,
                'is_recurring': True,
                'date_start': date(2026, 1, 1),
                'amount': amount,
            }
            for xml_id, amount in [
                ('l10n_ph_hr_payroll_sss_salary_loan_rule', 500.0),
                ('l10n_ph_hr_payroll_sss_calamity_loan_rule', 300.0),
                ('l10n_ph_hr_payroll_pag_ibig_mpl_rule', 400.0),
                ('l10n_ph_hr_payroll_pag_ibig_calamity_loan_rule', 200.0),
                ('l10n_ph_hr_payroll_pag_ibig_housing_loan_rule', 1000.0),
            ]
        ])

        payslip = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 15))
        payslip.action_validate()

        # Compared to test_average_wage_employee_payslip, GROSS and WITHH_TAX are untouched:
        # the loans are post-tax, so they only reduce the take home pay, by 2400.0 in total.
        payslip_results = {
            'BASIC': 15000.0,
            'OB': 0.0,
            'SSS_CONTRIB': -750.0,
            'PHILHEALTH_CONTRIB': -375.0,
            'PAG_IBIG_CONTRIB': -100.0,
            'GROSS': 13775.0,
            'WITHH_TAX': -503.7,
            'SSS_SALARY_LOAN': -500.0,
            'SSS_CALAMITY_LOAN': -300.0,
            'PAGIBIG_MPL': -400.0,
            'PAGIBIG_CALAMITY_LOAN': -200.0,
            'PAGIBIG_HOUSING_LOAN': -1000.0,
            'NET': 10871.3,
            'SSS_ER_CONTRIB': 1500.0,
            'SSS_EC_CONTRIB': 15.0,
            'PHILHEALTH_ER_CONTRIB': 375.0,
            'PAG_IBIG_ER_CONTRIB': 100.0,
            '13THMONTHPROVISION': 1250.0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_loan_deduction_remaining_amount(self):
        """ Test that the remaining amount of a loan goes down by the amount deducted on each paid payslip. """
        self._set_test_employee(self.average_employee)
        loan = self.env['hr.salary.attachment'].create({
            'employee_id': self.average_employee.id,
            'salary_rule_id': self.env.ref('l10n_ph_hr_payroll.l10n_ph_hr_payroll_sss_salary_loan_rule').id,
            'is_recurring': False,
            'date_start': date(2026, 1, 1),
            'amount': 1200.0,
        })
        self.assertEqual(loan.remaining_amount, 1200.0)

        # The last installment is capped to whatever is left to repay, instead of the full 500.
        for date_from, date_to, installment, deducted, remaining in [
            (date(2026, 1, 1), date(2026, 1, 15), 500.0, -500.0, 700.0),
            (date(2026, 1, 16), date(2026, 1, 31), 500.0, -500.0, 200.0),
            (date(2026, 2, 1), date(2026, 2, 15), None, -200.0, 0.0),
        ]:
            payslip = self._generate_payslip(date_from, date_to)
            if installment:
                payslip.input_line_ids.filtered(lambda line: line.code == 'SSS_SALARY_LOAN').amount = installment
                payslip.compute_sheet()
            payslip.action_validate()
            payslip.action_payslip_paid()
            self.assertEqual(payslip._get_line_values(['SSS_SALARY_LOAN'])['SSS_SALARY_LOAN'][payslip.id]['total'], deducted)
            self.assertEqual(loan.remaining_amount, remaining, 'Remaining amount = total amount - amount already deducted.')

        self.assertEqual(loan.paid_amount, 1200.0)
        self.assertEqual(loan.state, '2_close', 'A fully repaid loan is closed automatically.')
