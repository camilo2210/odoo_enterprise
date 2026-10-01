# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSalaryRulesMonthly(TestL10NHkHrPayrollAccountCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.resource_calendar_20_hours_per_week = cls.resource_calendar.copy({
            'name': "Test Calendar : 20 Hours/Week",
            'hours_per_day': 4,
            'hours_per_week': 20,
            'full_time_required_hours': 40,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '5', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                (0, 0, {'dayofweek': '6', 'hour_from': 8, 'hour_to': 12, 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
            ]
        })

    def test_001_a_regular_payslip(self):
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))

        self.assertEqual(len(payslip.worked_days_line_ids), 2)
        self.assertEqual(len(payslip.input_line_ids), 0)

        self._validate_worked_days(payslip, {
            '002.00': (22.0, 176.0, 14193.55),
            'HKLEAVE600': (9.0, 72.0, 5806.45),
        })

        payslip_results = {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'ERMC': -1010.0, 'NET': 20200.0, 'MEA': 20200.0}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_001_b_moving_daily_wage_computation(self):
        hk_annual_leave_allocation = self.env['hr.leave.allocation'].create({
            'name': 'HK Annual Leave Allocation',
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_hk_work_entry_type_annual_leave').id,
            'number_of_days': 10,
            'employee_id': self.employee.id,
            'state': 'confirm',
            'date_from': '2023-01-01',
        })
        hk_annual_leave_allocation.action_approve()
        leaves_to_create = [
            (datetime(2023, 3, 7), datetime(2023, 3, 7), self.env.ref('hr_work_entry.hk_work_entry_type_unpaid_leave')),
            (datetime(2023, 4, 11), datetime(2023, 4, 11), self.env.ref('hr_work_entry.l10n_hk_work_entry_type_annual_leave')),
        ]
        for date_from, date_to, work_entry_type in leaves_to_create:
            self._generate_leave(self.employee, date_from, date_to, work_entry_type)
        results = {
            1: {
                'moving_daily_wage': 0,
                'payslip': {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'ERMC': -1010.0, 'NET': 20200.0, 'MEA': 20200.0}
            },
            2: {
                'moving_daily_wage': 651.61,
                'payslip': {'BASIC': 20000.0, 'COMMISSION': 10000.0, 'ALW.INT': 200.0, '713_GROSS': 30200.0, 'GROSS': 30200.0, 'EEMC': -1500.0, 'ERMC': -1500.0, 'NET': 28700.0, 'MEA': 28700.0},
            },
            3: {
                'moving_daily_wage': 854.24,
                'payslip': {'BASIC': 19354.84, 'ALW.INT': 193.55, '713_GROSS': 19548.39, 'GROSS': 19548.39, 'EEMC': -977.42, 'ERMC': -977.42, 'NET': 18570.97, 'MEA': 18570.97},
            },
            4: {
                'moving_daily_wage': 785.94,
                'payslip': {'BASIC': 20119.28, 'ALW.INT': 200.0, '713_GROSS': 20319.28, 'GROSS': 20319.28, 'EEMC': -1015.96, 'ERMC': -1015.96, 'NET': 19303.32, 'MEA': 19303.32},
            }
        }
        for month in range(1, 5):
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )
            if month == 2:
                commission_rule_id = self.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_fixed_commission')
                payslip._set_input_value(commission_rule_id.code, 10000)
                payslip.compute_sheet()

            self.assertEqual(len(payslip.worked_days_line_ids), 3 if month in [3, 4] else 2)

            self.assertAlmostEqual(payslip.l10n_hk_average_daily_wage,
                                   results[month]['moving_daily_wage'],
                                   delta=0.01,
                                   msg="Incorrect moving daily wage for the %s month payslip" % month)
            self._validate_payslip(payslip, results[month]['payslip'], skip_lines=True)
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_001_c_maternity_leave_payslip(self):
        leaves_to_create = [
            (datetime(2023, 3, 7), datetime(2023, 3, 13), self.env.ref('hr_work_entry.l10n_hk_work_entry_type_maternity_leave')),
            (datetime(2023, 3, 14), datetime(2023, 4, 11), self.env.ref('hr_work_entry.l10n_hk_work_entry_type_maternity_leave_80')),
        ]
        for date_from, date_to, work_entry_type in leaves_to_create:
            self._generate_leave(self.employee, date_from, date_to, work_entry_type)
        results = {
            3: {'BASIC': 26952.37, 'ALW.INT': 200.0, '713_GROSS': 27152.37, 'GROSS': 27152.37, 'EEMC': -1357.62, 'ERMC': -1357.62, 'NET': 25794.75, 'MEA': 25794.75},
            4: {'BASIC': 22158.09, 'ALW.INT': 200.0, '713_GROSS': 22358.09, 'GROSS': 22358.09, 'EEMC': -1117.9, 'ERMC': -1117.9, 'NET': 21240.19, 'MEA': 21240.19}
        }
        payslip = self._generate_payslip(
            date(2023, 2, 1),
            date(2023, 2, 28),
        )
        commission_rule_id = self.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_fixed_commission')
        payslip._set_input_value(commission_rule_id.code, 10000)
        payslip.compute_sheet()
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        payslip = self._generate_payslip(date(2023, 3, 1), date(2023, 3, 31))
        # TODO: could be wrong test, should be 5 days of HKLEAVE210 instead of 7, confirm with vin
        self._validate_worked_days(payslip, {
            'HKLEAVE210': (7.0, 56.0, 7549.99),
            'HKLEAVE211': (18.0, 144.0, 15531.41),
        }, skip_lines=True)
        maternity_leave_data = payslip._get_worked_days_line_values(['HKLEAVE211'], ['amount', 'number_of_days'], True)['HKLEAVE211']['sum']
        maternity_leave_daily_wage = maternity_leave_data['amount'] / maternity_leave_data['number_of_days']
        self._validate_payslip(payslip, results[3], skip_lines=True)
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        payslip = self._generate_payslip(date(2023, 4, 1), date(2023, 4, 30))
        self._validate_worked_days(payslip, {'HKLEAVE211': (11.0, 88.0, 9491.42)}, skip_lines=True)
        maternity_leave_data = payslip._get_worked_days_line_values(['HKLEAVE211'], ['amount', 'number_of_days'], True)['HKLEAVE211']['sum']
        self.assertAlmostEqual(maternity_leave_data['amount'] / maternity_leave_data['number_of_days'], maternity_leave_daily_wage, places=2)
        self._validate_payslip(payslip, results[4], skip_lines=True)
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

    def test_002_a_credit_time_payslip(self):
        self.version.write({
            'wage': 10000.0,
            'resource_calendar_id': self.resource_calendar_20_hours_per_week.id,
        })
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))

        self.assertEqual(len(payslip.worked_days_line_ids), 2)
        self.assertEqual(len(payslip.input_line_ids), 0)

        self._validate_worked_days(payslip, {
            '002.00': (22.0, 88.0, 7096.77),
            'HKLEAVE600': (9.0, 36.0, 2903.23),
        })

        payslip_results = {'BASIC': 10000.0, 'ALW.INT': 200.0, '713_GROSS': 10200.0, 'GROSS': 10200.0, 'ERMC': -510.0, 'NET': 10200.0, 'MEA': 10200.0}
        self._validate_payslip(payslip, payslip_results)

    def test_002_b_credit_time_moving_daily_wage(self):
        self.version.write({
            'wage': 10000.0,
            'resource_calendar_id': self.resource_calendar_20_hours_per_week.id,
        })

        results = {
            1: {
                'moving_daily_wage': 0,
                'payslip': {'BASIC': 10000.0, 'ALW.INT': 200.0, '713_GROSS': 10200.0, 'GROSS': 10200.0, 'ERMC': -510.0, 'NET': 10200.0, 'MEA': 10200.0},
            },
            2: {
                'moving_daily_wage': 329.03,
                'payslip': {'BASIC': 10000.0, 'ALW.INT': 200.0, '713_GROSS': 10200.0, 'GROSS': 10200.0, 'EEMC': -510.0, 'ERMC': -510.0, 'NET': 9690.0, 'MEA': 9690.0},
            }
        }

        for month in range(1, 3):
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )

            self.assertEqual(len(payslip.worked_days_line_ids), 2)
            self.assertEqual(len(payslip.input_line_ids), 0)

            self.assertAlmostEqual(payslip.l10n_hk_average_daily_wage,
                                   results[month]['moving_daily_wage'],
                                   delta=0.01,
                                   msg="Incorrect moving daily wage for the %s month payslip" % month)
            self._validate_payslip(payslip, results[month]['payslip'])
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_003_internet_allowance(self):
        self.version.write({
            'date_version': date(2023, 1, 10),
            'contract_date_start': date(2023, 1, 10),
        })
        self._generate_leave(
            self.employee,
            datetime(2023, 1, 18),
            datetime(2023, 1, 20),
            self.env.ref('hr_work_entry.hk_work_entry_type_unpaid_leave'))
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))

        self.assertEqual(len(payslip.worked_days_line_ids), 4)
        self.assertEqual(len(payslip.input_line_ids), 0)

        self._validate_worked_days(payslip, {
            '002.00': (13.0, 104.0, 8387.1),
            '158.00': (3.0, 24.0, 0.0),
            'HKLEAVE600': (6.0, 48.0, 3870.97),
            '000.00': (9.0, 72.0, 0.0),
        })

        payslip_results = {'BASIC': 12258.07, 'ALW.INT': 122.58, '713_GROSS': 12380.65, 'GROSS': 12380.65, 'ERMC': -619.03, 'NET': 12380.65, 'MEA': 12380.65}
        self._validate_payslip(payslip, payslip_results)

    def test_004_a_mpf_computation(self):
        payslip_results = {
            1: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'ERMC': -1010.0, 'NET': 20200.0, 'MEA': 20200.0},
            2: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0},
            3: {'BASIC': 20000.0, 'COMMISSION': 10000.0, 'ALW.INT': 200.0, '713_GROSS': 30200.0, 'GROSS': 30200.0, 'EEMC': -1500.0, 'ERMC': -1500.0, 'NET': 28700.0, 'MEA': 28700.0},
        }
        for month in range(1, 4):
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )
            if month == 3:
                commission_rule_id = self.env.ref('l10n_hk_hr_payroll.cap57_employees_salary_fixed_commission')
                payslip._set_input_value(commission_rule_id.code, 10000)
                payslip.compute_sheet()
            self._validate_payslip(payslip, payslip_results[month], skip_lines=True)
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_004_b_mpf_first_contribution(self):
        self.version.write({
            'date_version': date(2023, 2, 1),
            'contract_date_start': date(2023, 2, 1),
        })
        payslip_results = {
            2: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'ERMC': -1010.0, 'NET': 20200.0, 'MEA': 20200.0},
            3: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'ERMC': -1010.0, 'NET': 20200.0, 'MEA': 20200.0},
            4: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0},
            5: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0},
        }
        for month in range(2, 6):
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )
            self._validate_payslip(payslip, payslip_results[month], skip_lines=True)
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_004_c_mpf_volunteer_contribution_fixed(self):
        self.version.write({
            'wage': 21000.0,
            'l10n_hk_internet': 0.0,
            "l10n_hk_member_class_id": self.member_class.id,
        })
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))
        payslip.action_payslip_done()
        payslip.action_payslip_paid()
        self.employee.l10n_hk_member_class_ct_eevc_id.contribution_option = 'percentage'
        inputs = {
            2: {
                'wage': 21000.0,
                'commission': 0.0,
                'vc_percentage': 5,
            },
            3: {
                'wage': 21000.0,
                'commission': 0.0,
                'vc_percentage': 5,
            },
            4: {
                'wage': 32000.0,
                'commission': 0.0,
                'vc_percentage': 5,
            },
            5: {
                'wage': 22000.0,
                'commission': 0.0,
                'vc_percentage': 3,
            },
            6: {
                'wage': 22000.0,
                'commission': 13000.0,
                'vc_percentage': 3,
            },
        }
        payslip_results = {
            2: {'BASIC': 21000.0, '713_GROSS': 21000.0, 'GROSS': 21000.0, 'EEMC': -1050.0, 'ERMC': -1050.0, 'EEVC': -1050.0, 'ERVC': -1050.0, 'NET': 18900.0, 'MEA': 18900.0},
            3: {'BASIC': 21000.0, '713_GROSS': 21000.0, 'GROSS': 21000.0, 'EEMC': -1050.0, 'ERMC': -1050.0, 'EEVC': -1050.0, 'ERVC': -1050.0, 'NET': 18900.0, 'MEA': 18900.0},
            4: {'BASIC': 32000.0, '713_GROSS': 32000.0, 'GROSS': 32000.0, 'EEMC': -1500.0, 'ERMC': -1500.0, 'EEVC': -1600.0, 'ERVC': -1600.0, 'NET': 28900.0, 'MEA': 28900.0},
            5: {'BASIC': 22000.0, '713_GROSS': 22000.0, 'GROSS': 22000.0, 'EEMC': -1100.0, 'ERMC': -1100.0, 'EEVC': -660.0, 'ERVC': -660.0, 'NET': 20240.0, 'MEA': 20240.0},
            6: {'BASIC': 22000.0, 'COMMISSION': 13000.0, '713_GROSS': 35000.0, 'GROSS': 35000.0, 'EEMC': -1500.0, 'ERMC': -1500.0, 'EEVC': -1050.0, 'ERVC': -1050.0, 'NET': 32450.0, 'MEA': 32450.0}
        }
        for month in range(2, 7):
            self.employee.l10n_hk_member_class_ct_eevc_id.amount = inputs[month]['vc_percentage']
            self.version.write({'wage': inputs[month]['wage']})
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )
            if inputs[month]['commission']:
                payslip._set_input_value('COMMISSION', inputs[month]['commission'])
                payslip.compute_sheet()
            self._validate_payslip(payslip, payslip_results[month])
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_004_d_mpf_volunteer_contribution_cap(self):
        self.version.write({
            'wage': 21000.0,
            'l10n_hk_internet': 0.0,
            "l10n_hk_member_class_id": self.member_class.id,
        })
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))
        payslip.action_payslip_done()
        payslip.action_payslip_paid()
        inputs = {
            2: {
                'wage': 21000.0,
                'commission': 0.0
            },
            3: {
                'wage': 21000.0,
                'commission': 0.0
            },
            4: {
                'wage': 32000.0,
                'commission': 0.0
            },
            5: {
                'wage': 22000.0,
                'commission': 0.0
            },
            6: {
                'wage': 22000.0,
                'commission': 13000.0
            },
        }
        payslip_results = {
            2: {'BASIC': 21000.0, '713_GROSS': 21000.0, 'GROSS': 21000.0, 'EEMC': -1050.0, 'ERMC': -1050.0, 'EEVC': 0, 'ERVC': 0, 'NET': 19950.0, 'MEA': 19950.0},
            3: {'BASIC': 21000.0, '713_GROSS': 21000.0, 'GROSS': 21000.0, 'EEMC': -1050.0, 'ERMC': -1050.0, 'EEVC': 0, 'ERVC': 0, 'NET': 19950.0, 'MEA': 19950.0},
            4: {'BASIC': 32000.0, '713_GROSS': 32000.0, 'GROSS': 32000.0, 'EEMC': -1500.0, 'ERMC': -1500.0, 'EEVC': -100.0, 'ERVC': -100.0, 'NET': 30400.0, 'MEA': 30400.0},
            5: {'BASIC': 22000.0, '713_GROSS': 22000.0, 'GROSS': 22000.0, 'EEMC': -1100.0, 'ERMC': -1100.0, 'EEVC': 0, 'ERVC': 0, 'NET': 20900.0, 'MEA': 20900.0},
            6: {'BASIC': 22000.0, 'COMMISSION': 13000.0, '713_GROSS': 35000.0, 'GROSS': 35000.0, 'EEMC': -1500.0, 'ERMC': -1500.0, 'EEVC': -250.0, 'ERVC': -250.0, 'NET': 33250.0, 'MEA': 33250.0},
        }
        for month in range(2, 7):
            self.version.write({'wage': inputs[month]['wage']})
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )
            if inputs[month]['commission']:
                payslip._set_input_value('COMMISSION', inputs[month]['commission'])
                payslip.compute_sheet()
            self._validate_payslip(payslip, payslip_results[month])
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_004_e_mpf_first_contribution_special_case(self):
        self.version.write({
            'date_version': date(2023, 7, 3),
            'contract_date_start': date(2023, 7, 3),
        })
        payslip_results = {
            7: {'BASIC': 18709.68, 'ALW.INT': 187.1, '713_GROSS': 18896.78, 'GROSS': 18896.78, 'ERMC': -944.84, 'NET': 18896.78, 'MEA': 18896.78},
            8: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'ERMC': -1010.0, 'NET': 20200.0, 'MEA': 20200.0},
            9: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0},
            10: {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'EEMC': -1010.0, 'ERMC': -1010.0, 'NET': 19190.0, 'MEA': 19190.0},
        }
        for month in range(7, 11):
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )
            self._validate_payslip(payslip, payslip_results[month])
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_004_f_mpf_below_mpf_threshold_include_ermc(self):
        self.version.write({
            'wage': 5000.0,
            'l10n_hk_internet': 0.0,
        })
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        payslip_results = {
            2: {'BASIC': 5000.0, '713_GROSS': 5000.0, 'GROSS': 5000.0, 'ERMC': -250, 'NET': 5000.0, 'MEA': 5000.0},
            3: {'BASIC': 5000.0, '713_GROSS': 5000.0, 'GROSS': 5000.0, 'ERMC': -250, 'NET': 5000.0, 'MEA': 5000.0}
        }

        for month in range(2, 4):
            payslip = self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            )
            self._validate_payslip(payslip, payslip_results[month])
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

    def test_004_g_mpf_contribution_age_boundaries(self):
        date_from = date(2023, 2, 1)
        date_to = date(2023, 2, 28)
        contributes_results = {
            'BASIC': 20000.0,
            '713_GROSS': 20000.0,
            'GROSS': 20000.0,
            'EEMC': -1000.0,
            'ERMC': -1000.0,
            'NET': 19000.0,
            'MEA': 19000.0,
        }
        no_contribution_results = {
            'BASIC': 20000.0,
            '713_GROSS': 20000.0,
            'GROSS': 20000.0,
            'NET': 20000.0,
            'MEA': 20000.0,
        }
        cases = [
            ('no_birthday', None, contributes_results),
            ('turns_18_on_date_to', date(2005, 2, 28), contributes_results),
            ('under_18_entire_period', date(2005, 3, 1), no_contribution_results),
            ('turns_65_during_period', date(1958, 2, 2), contributes_results),
            ('turns_65_on_date_from', date(1958, 2, 1), no_contribution_results),
            ('already_65_before_period', date(1958, 1, 31), no_contribution_results),
        ]
        common_contract_fields = {
            'date_version': date(2023, 1, 1),
            'contract_date_start': date(2023, 1, 1),
            'wage': 20000.0,
            'l10n_hk_internet': 0.0,
            'l10n_hk_mpf_scheme_id': self.mpf_scheme.id,
            'l10n_hk_mpf_registration_status': 'registered',
            'l10n_hk_mpf_contribution_start': 'immediate',
            'l10n_hk_mpf_scheme_join_date': date(2023, 1, 1),
        }

        for name, birthday, expected_results in cases:
            with self.subTest(name=name):
                employee = self._setup_employee(
                    country=self.env.ref('base.hk'),
                    structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
                    resource_calendar=self.resource_calendar,
                    contract_fields=common_contract_fields,
                    employee_fields={'birthday': birthday},
                )
                payslip = self._generate_payslip(
                    date_from,
                    date_to,
                    version_id=employee.version_id.id,
                    employee_id=employee.id,
                )
                self._validate_payslip(payslip, expected_results)

    def test_005_a_end_of_year_payment(self):
        for month in range(1, 12):
            self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            ).action_payslip_done()

        payslip = self._generate_payslip(date(2023, 12, 1), date(2023, 12, 31))
        payslip_results = {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'END_OF_YEAR_PAYMENT': 20235.28, 'GROSS': 40435.28, 'EEMC': -1500.0, 'ERMC': -1500.0, 'NET': 38935.28, 'MEA': 38935.28}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_005_b_incomplete_year_end_of_year_payment(self):
        self.version.write({
            'date_version': date(2023, 7, 3),
            'contract_date_start': date(2023, 7, 3),
        })
        for month in range(7, 12):
            self._generate_payslip(
                date(2023, month, 1),
                date(2023, month, 1) + relativedelta(day=31),
            ).action_payslip_done()

        payslip = self._generate_payslip(date(2023, 12, 1), date(2023, 12, 31))
        payslip_results = {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'END_OF_YEAR_PAYMENT': 10013.69, 'GROSS': 30213.69, 'EEMC': -1500.0, 'ERMC': -1500.0, 'NET': 28713.69, 'MEA': 28713.69}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_contract_change(self):
        """
        Test an employee whose contract is updated in the middle of the month.
        The payrun will contain two payslips, and we need to make sure that the amounts of various benefits aren't double.
        """
        self.version.write({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': date(2026, 1, 15),
            'wage': 40000,
            'l10n_hk_mpf_scheme_id': self.mpf_scheme.id,
            "l10n_hk_mpf_contribution_start": "immediate",
            "l10n_hk_mpf_registration_status": "registered",
            "l10n_hk_member_class_id": self.member_class.id,
            "l10n_hk_mpf_scheme_join_date": date(2025, 10, 1),
        })
        self.version.l10n_hk_member_class_ct_ervc2_id = self.env['l10n_hk.member.class.contribution.type'].create({
            'member_class_id': self.member_class.id,
            'contribution_type': 'employer_2',
            'contribution_option': 'fixed',
            'amount': 200,
        })
        self.employee.create_version({
            'date_version': date(2026, 1, 16),
            'contract_date_start': date(2026, 1, 16),
            'wage': 40000,
        })

        payrun = self.env['hr.payslip.run'].create({
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 1, 31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids.sorted('date_from asc')
        self.assertEqual(len(payslips), 2)
        # Assert the first payslip's line
        first_payslip_results = {
            'BASIC': 19354.84,
            'ALW.INT': 96.77,
            '713_GROSS': 19451.61,
            'GROSS': 19451.61,
            'EEMC': -972.58,
            'ERMC': -972.58,
            'EEVC': 0.0,
            'ERVC': 0.0,
            'ERVC2': -96.77,
            'NET': 18479.03,
            'MEA': 18479.03,
        }
        self._validate_payslip(payslips[0], first_payslip_results)
        # And the second
        second_payslip_results = {
            'BASIC': 20645.16,
            'ALW.INT': 103.23,
            '713_GROSS': 20748.39,
            'GROSS': 20748.39,
            'EEMC': -527.42,
            'ERMC': -527.42,
            'EEVC': -510.0,
            'ERVC': -510.0,
            'ERVC2': -103.23,
            'NET': 19710.97,
            'MEA': 19710.97,
        }
        self._validate_payslip(payslips[1], second_payslip_results)
        # As comparison, we'll also do a payslip for another month of same length.
        date_start = date(2026, 3, 1)
        payrun = self.env['hr.payslip.run'].create({
            'date_start': date_start,
            'date_end': date_start + relativedelta(day=31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids
        control_payslip_results = {
            'BASIC': 40000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 40200.0,
            'GROSS': 40200.0,
            'EEMC': -1500.0,
            'ERMC': -1500.0,
            'EEVC': -510.0,
            'ERVC': -510.0,
            'ERVC2': -200.0,
            'NET': 38190.0,
            'MEA': 38190.0,
        }
        self._validate_payslip(payslips, control_payslip_results)
        # And to make sure we're all good, we now sum the two half month payslip and compare the result with the full month one!
        for rule, control_value in control_payslip_results.items():
            self.assertEqual(
                first_payslip_results[rule] + second_payslip_results[rule], control_value
            )

    def test_contract_change_middle_monthly_payrun(self):
        """
        Same as above, but the payslip is between two middle of months.
        """
        self.version.write({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': date(2026, 1, 31),
            'wage': 40000,
        })
        self.employee.create_version({
            'date_version': date(2026, 2, 1),
            'contract_date_start': date(2026, 2, 1),
            'wage': 40000,
        })

        payrun = self.env['hr.payslip.run'].create({
            'date_start': date(2026, 1, 15),
            'date_end': date(2026, 2, 15),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids.sorted('date_from asc')
        self.assertEqual(len(payslips), 2)
        # Assert the first payslip's line
        first_payslip_results = {
            'BASIC': 21250.0,
            'ALW.INT': 106.25,
            '713_GROSS': 21356.25,
            'GROSS': 21356.25,
            'EEMC': -1067.81,
            'ERMC': -1067.81,
            'NET': 20288.44,
            'MEA': 20288.44,
        }
        self._validate_payslip(payslips[0], first_payslip_results)
        # And the second
        second_payslip_results = {
            'BASIC': 18750.0,
            'ALW.INT': 93.75,
            '713_GROSS': 18843.75,
            'GROSS': 18843.75,
            'EEMC': -432.19,
            'ERMC': -432.19,
            'NET': 18411.56,
            'MEA': 18411.56,
        }
        self._validate_payslip(payslips[1], second_payslip_results)
        # As comparison, we'll also do a payslip for another month of same length.
        date_start = date(2026, 3, 1)
        payrun = self.env['hr.payslip.run'].create({
            'date_start': date_start,
            'date_end': date_start + relativedelta(day=31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids
        control_payslip_results = {
            'BASIC': 40000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 40200.0,
            'GROSS': 40200.0,
            'EEMC': -1500.0,
            'ERMC': -1500.0,
            'NET': 38700.0,
            'MEA': 38700.0,
        }
        self._validate_payslip(payslips, control_payslip_results)
        # And to make sure we're all good, we now sum the two half month payslip and compare the result with the full month one!
        for rule, control_value in control_payslip_results.items():
            self.assertEqual(
                first_payslip_results[rule] + second_payslip_results[rule], control_value
            )

    def test_contract_change_rent(self):
        """
        Test the case of a contract change where rent is involved.
        In this scenario, the half month wage shouldn't be enough to cover the whole rent amount; but we expect the two
        halves to make up for the whole amount.
        """
        self.version.write({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': date(2026, 1, 15),
            'wage': 40000,
        })
        rental = self._create_test_rental(self.version.employee_id, {'amount': 25000})
        rental.action_confirm_rental()
        rental.valid_up_to_date = date(2027, 1, 31)
        self.employee.create_version({
            'date_version': date(2026, 1, 16),
            'contract_date_start': date(2026, 1, 16),
            'wage': 40000,
        })

        payrun = self.env['hr.payslip.run'].create({
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 1, 31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids.sorted('date_from asc')
        self.assertEqual(len(payslips), 2)
        # Assert the first payslip's line
        first_payslip_results = {
            'HRA': 15650.04,
            'BASIC': 3704.8,
            'ALW.INT': 96.77,
            '713_GROSS': 19451.61,
            'GROSS': 19451.61,
            'EEMC': -972.58,
            'ERMC': -972.58,
            'NET': 18479.03,
            'MEA': 18479.03,
        }
        self._validate_payslip(payslips[0], first_payslip_results)
        # And the second
        second_payslip_results = {
            'HRA': 9349.96,
            'BASIC': 11295.2,
            'ALW.INT': 103.23,
            '713_GROSS': 20748.39,
            'GROSS': 20748.39,
            'EEMC': -527.42,
            'ERMC': -527.42,
            'NET': 20220.97,
            'MEA': 20220.97,
        }
        self._validate_payslip(payslips[1], second_payslip_results)
        # As comparison, we'll also do a payslip for another month of same length.
        date_start = date(2026, 3, 1)
        payrun = self.env['hr.payslip.run'].create({
            'date_start': date_start,
            'date_end': date_start + relativedelta(day=31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids
        control_payslip_results = {
            'HRA': 25000.0,
            'BASIC': 15000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 40200.0,
            'GROSS': 40200.0,
            'EEMC': -1500.0,
            'ERMC': -1500.0,
            'NET': 38700.0,
            'MEA': 38700.0,
        }
        self._validate_payslip(payslips, control_payslip_results)
        # And to make sure we're all good, we now sum the two half month payslip and compare the result with the full month one!
        for rule, control_value in control_payslip_results.items():
            self.assertEqual(
                first_payslip_results[rule] + second_payslip_results[rule], control_value
            )

    def test_contract_change_rent_copay(self):
        """
        Test the case of a contract change where a co-pay rent is involved.
        In this scenario, the half month wage shouldn't be enough to cover the whole rent amount; but we expect the two
        halves to make up for the whole amount.
        """
        self.version.write({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': date(2026, 1, 15),
            'wage': 40000,
        })
        rental = self._create_test_rental(self.version.employee_id, {'lease_type': 'co_payment', 'co_pay_amount': 25000, 'amount': 50000})
        rental.action_confirm_rental()
        self.employee.create_version({
            'date_version': date(2026, 1, 16),
            'contract_date_start': date(2026, 1, 16),
            'wage': 40000,
        })

        payrun = self.env['hr.payslip.run'].create({
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 1, 31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids.sorted('date_from asc')
        self.assertEqual(len(payslips), 2)
        # Assert the first payslip's line
        first_payslip_results = {
            'BASIC': 19354.84,
            'ALW.INT': 96.77,
            '713_GROSS': 19451.61,
            'GROSS': 19451.61,
            'EEMC': -972.58,
            'ERMC': -972.58,
            'NET': 0.0,
            'HEPR': 50000.0,
            'HC': -18479.03,
            'MEA': 0.0,
        }
        self._validate_payslip(payslips[0], first_payslip_results)
        # And the second
        second_payslip_results = {
            'BASIC': 20645.16,
            'ALW.INT': 103.23,
            '713_GROSS': 20748.39,
            'GROSS': 20748.39,
            'EEMC': -527.42,
            'ERMC': -527.42,
            'NET': 13700.0,
            'HEPR': 0.0,
            'HC': -6520.97,
            'MEA': 13700.0,
        }
        self._validate_payslip(payslips[1], second_payslip_results)
        # As comparison, we'll also do a payslip for another month of same length.
        date_start = date(2026, 3, 1)
        payrun = self.env['hr.payslip.run'].create({
            'date_start': date_start,
            'date_end': date_start + relativedelta(day=31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids
        control_payslip_results = {
            'BASIC': 40000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 40200.0,
            'GROSS': 40200.0,
            'EEMC': -1500.0,
            'ERMC': -1500.0,
            'NET': 13700.0,
            'HEPR': 50000.0,
            'HC': -25000.0,
            'MEA': 13700.0,
        }
        self._validate_payslip(payslips, control_payslip_results)
        # And to make sure we're all good, we now sum the two half month payslip and compare the result with the full month one!
        for rule, control_value in control_payslip_results.items():
            self.assertEqual(
                first_payslip_results[rule] + second_payslip_results[rule], control_value
            )

    def test_contract_change_rent_employer_paid(self):
        """
        Test the case of a contract change where an employer paid rent is involved.
        In this scenario, the employer pays the full amount in the first payslip.
        """
        self.version.write({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': date(2026, 1, 15),
            'wage': 40000,
        })
        rental = self._create_test_rental(self.version.employee_id, {'lease_type': 'direct_payment', 'amount': 50000})
        rental.action_confirm_rental()
        self.employee.create_version({
            'date_version': date(2026, 1, 16),
            'contract_date_start': date(2026, 1, 16),
            'wage': 40000,
        })

        payrun = self.env['hr.payslip.run'].create({
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 1, 31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids.sorted('date_from asc')
        self.assertEqual(len(payslips), 2)
        # Assert the first payslip's line
        first_payslip_results = {
            'BASIC': 19354.84,
            'ALW.INT': 96.77,
            '713_GROSS': 19451.61,
            'GROSS': 19451.61,
            'EEMC': -972.58,
            'ERMC': -972.58,
            'NET': 18479.03,
            'HEPR': 50000.0,
            'MEA': 18479.03,
        }
        self._validate_payslip(payslips[0], first_payslip_results)
        # And the second
        second_payslip_results = {
            'BASIC': 20645.16,
            'ALW.INT': 103.23,
            '713_GROSS': 20748.39,
            'GROSS': 20748.39,
            'EEMC': -527.42,
            'ERMC': -527.42,
            'NET': 20220.97,
            'HEPR': 0.0,
            'MEA': 20220.97,
        }
        self._validate_payslip(payslips[1], second_payslip_results)
        # As comparison, we'll also do a payslip for another month of same length.
        date_start = date(2026, 3, 1)
        payrun = self.env['hr.payslip.run'].create({
            'date_start': date_start,
            'date_end': date_start + relativedelta(day=31),
            'company_id': self.env.company.id,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
        })
        payrun._generate_payslips()
        payslips = payrun.slip_ids
        control_payslip_results = {
            'BASIC': 40000.0,
            'ALW.INT': 200.0,
            '713_GROSS': 40200.0,
            'GROSS': 40200.0,
            'EEMC': -1500.0,
            'ERMC': -1500.0,
            'NET': 38700.0,
            'HEPR': 50000.0,
            'MEA': 38700.0,
        }
        self._validate_payslip(payslips, control_payslip_results)
        # And to make sure we're all good, we now sum the two half month payslip and compare the result with the full month one!
        for rule, control_value in control_payslip_results.items():
            self.assertEqual(
                first_payslip_results[rule] + second_payslip_results[rule], control_value
            )

    def test_sick_leaves_over_rest_days(self):
        """ Validate that a sick leave doesn't take precedence over a rest day. """
        date_start = date(2025, 1, 1)
        self.version.write({
            'date_version': date_start,
            'contract_date_start': date_start,
        })

        self._generate_leave(
            self.employee,
            date(2025, 10, 3),
            date(2025, 10, 7),
            self.env.ref('hr_work_entry.l10n_hk_work_entry_type_sick_leave_80'))
        payslip = self._generate_payslip(date(2025, 10, 1), date(2025, 10, 31))
        # In the 31 days of October 2025 we have:
        # 20 work days (1-2, 8-10, 13-17, 20-24, 27-31)
        # 8 weekend days (4-5, 11-12, 18-19, 25-26)
        # 3 sick leave day (3, 6-7). The sick leave on the 4-5 are no taking precedence over the weekend work entry.
        self._validate_worked_days(payslip, {
            'HKLEAVE111': (3.0, 24.0, 0.0),  # ADW is zero due to no previous payslips, but this doesn't affect the test.
            'HKLEAVE600': (8.0, 64.0, 5161.29),
            '002.00': (20.0, 160.0, 12903.23),
        })

    def test_employer_cost(self):
        """ Test that employer cost is the sum of the amounts the employer actually pays out. """
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))
        payslip_results = {'BASIC': 20000.0, 'ALW.INT': 200.0, '713_GROSS': 20200.0, 'GROSS': 20200.0, 'ERMC': -1010.0, 'NET': 20200.0, 'MEA': 20200.0}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

        employer_cost_codes = {
            'GROSS', 'RETIREMENT_PAY', 'PENSION_PAYOUT', 'EDU_ALLOWANCE',
            'TAX_PAID_BY_EMP', 'HEPR', 'REIMBURSEMENT', 'EXPENSES',
        }
        expected_employer_cost = sum(payslip.line_ids.filtered(lambda line: line.code in employer_cost_codes).mapped('total'))
        self.assertEqual(payslip.employer_cost, expected_employer_cost)
        self.assertEqual(payslip.employer_cost, 20200.0)

    def test_employer_cost_non_employee(self):
        """ Test that employer cost covers the fees paid to a non-employee, without the withheld amount. """
        non_employee = self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_non_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2023, 1, 1),
                'contract_date_start': date(2023, 1, 1),
                'employee_type_id': self.env.ref('l10n_hk_hr_payroll.l10n_hk_contract_type_non_employee').id,
                'wage': 0.0,
            },
        )
        payslip = self.env['hr.payslip'].create({
            'name': 'Non Employee Payslip',
            'employee_id': non_employee.id,
            'struct_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_non_employee_salary').id,
            'date_from': date(2023, 1, 1),
            'date_to': date(2023, 1, 31),
        })
        inputs = {
            'SUBCON_FEE': 10000.0,
            'CONSULT_FEE': 5000.0,
            'REIMBURSEMENT': 500.0,
            'EXPENSES': 300.0,
            'WITHHELD': 2000.0,
        }
        for code, amount in inputs.items():
            payslip._set_input_value(code, amount)
        payslip.compute_sheet()

        payslip_results = {
            'SUBCON_FEE': 10000.0, 'CONSULT_FEE': 5000.0, 'REIMBURSEMENT': 500.0,
            'EXPENSES': 300.0, 'GROSS': 15000.0, 'WITHHELD': -2000.0, 'NET': 13800.0,
        }
        self._validate_payslip(payslip, payslip_results)

        # The fees are only counted once, and the amount withheld is still paid out by the
        # employer, to the IRD instead of to the non-employee.
        self.assertEqual(payslip.employer_cost, 15800.0)

    def test_work_injury_sick_leave(self):
        """ Validate that a work injury sick leave is correctly recorded and paid as per the Cap. 282. """
        date_start = date(2025, 1, 1)
        self.version.write({
            'date_version': date_start,
            'contract_date_start': date_start,
            'l10n_hk_internet': 0.0,  # Makes it easy to assert the exact behavior.
            'wage': 80000,
        })

        # We need some payslips over the past 12 months to allow testing the calculation.
        for dt in rrule(MONTHLY, dtstart=date(2025, 1, 1), until=date(2025, 9, 1)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()

        self._generate_leave(
            self.employee,
            date(2025, 10, 1),
            date(2025, 10, 31),
            self.env.ref('hr_work_entry.l10n_hk_work_entry_type_work_injury_sick_leave_80'),
        )
        payslip = self._generate_payslip(date(2025, 10, 1), date(2025, 10, 31))
        # The work injury itself takes precedence over weekends and such.
        self._validate_worked_days(payslip, {
            'HKLEAVE112': (31.0, 248.0, 64000.0),  # 80000 of base salary * 0.8 => 16000
        })
        payslip.compute_sheet()
        # The work injury amount is non-taxable, so it falls straight into the net without counting for mpf, ...
        self._validate_payslip(payslip, {
            'BASIC': 0.0,
            '713_GROSS': 0.0,
            'GROSS': 0.0,
            'ERMC': 0.0,
            'WORK_INJURY': 64000.0,
            'NET': 64000.0,  # The work injury amount is non-taxable, so it falls straight into the net without counting for mpf, ...
            'MEA': 64000.0,
        })
        # The employee worked for an afternoon
        payslip._set_input_value('POST_ACCIDENT_EARNINGS', 8000)
        self._validate_worked_days(payslip, {
            'HKLEAVE112': (31.0, 248.0, 57600.0),  # 80000 as above - 8000 (72000) * 0.8 => 57600
        })
        payslip.compute_sheet()
        # Post-accident earnings, them, are taxable.
        self._validate_payslip(payslip, {
            'BASIC': 0.0,
            'POST_ACCIDENT_EARNINGS': 8000.0,
            '713_GROSS': 8000.0,
            'GROSS': 8000.0,
            'EEMC': -400.0,
            'ERMC': -400.0,
            'WORK_INJURY': 57600.0,
            'NET': 65200.0,
            'MEA': 65200.0,
        })

    def test_work_injury_sick_leave_over_multiple_months(self):
        """
        When an injury sick leave spans multiple months, the baseline used for the calculation must be from before
        the start of the injury.
        All payslips during the injury period should be excluded, as to not affect the calculation by counting a reduced
        wage month.
        """
        date_start = date(2025, 1, 1)
        self.version.write({
            'date_version': date_start,
            'contract_date_start': date_start,
            'l10n_hk_internet': 0.0,  # Makes it easy to assert the exact behavior.
            'wage': 80000,
        })

        # We need some payslips over the past 12 months to allow testing the calculation.
        for dt in rrule(MONTHLY, dtstart=date(2025, 1, 1), until=date(2025, 9, 1)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()

        self._generate_leave(
            self.employee,
            date(2025, 10, 1),
            date(2025, 12, 31),
            self.env.ref('hr_work_entry.l10n_hk_work_entry_type_work_injury_sick_leave_80'),
        )
        payslip = self._generate_payslip(date(2025, 10, 1), date(2025, 10, 31))
        payslip._set_input_value('POST_ACCIDENT_EARNINGS', 8000)
        payslip.action_payslip_done()
        payslip = self._generate_payslip(date(2025, 11, 1), date(2025, 11, 30))
        payslip._set_input_value('POST_ACCIDENT_EARNINGS', 4000)
        payslip.action_payslip_done()
        payslip = self._generate_payslip(date(2025, 12, 1), date(2025, 12, 31))
        payslip._set_input_value('POST_ACCIDENT_EARNINGS', 10000)
        payslip.compute_sheet()
        # Even though we had two months of 713 gross being very low (only the post accident earnings), the third month
        # Still has the correct baseline as it is based on the wages at the time the accident happened.
        self._validate_worked_days(payslip, {
            'HKLEAVE112': (31.0, 248.0, 56000.0),  # 80000 as above - 10000 (70000) * 0.8 => 56000
        })
        self._validate_payslip(payslip, {
            'BASIC': 0.0,
            'END_OF_YEAR_PAYMENT': 68583.6,
            'POST_ACCIDENT_EARNINGS': 10000.0,
            '713_GROSS': 10000.0,
            'GROSS': 78583.6,
            'EEMC': -1500.0,
            'ERMC': -1500.0,
            'WORK_INJURY': 56000.0,
            'NET': 133083.6,
            'MEA': 133083.6,
        })
