# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.hr_payroll.tests.common import TestPayrollBase


@tagged('post_install_l10n', 'post_install', '-at_install', 'l10n_vn_hr_payroll')
class TestL10nVnPayslip(TestPayrollBase):
    """Vietnamese regular pay structure.

    The expected payslip lines live in tests/test_files/payslips/test_payslip_computation/<test>.json,
    regenerate them with the ',SAVE_JSON' pseudo tag (see hr_payroll.tests.common).

    Unless stated otherwise, the employee earns 17,600,000 VND on a 40 hours week: on a 22 working
    days month (176 hours) the hourly wage is exactly 100,000 VND, which keeps the overtime figures
    readable. March 2026, June 2026, July 2026 and September 2026 all have 22 working days.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.vn'),
            structure=cls.env.ref('l10n_vn_hr_payroll.hr_payroll_structure_vn_employee_salary'),
            structure_type=cls.env.ref('l10n_vn_hr_payroll.structure_type_employee_vn'),
            version_fields={
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'wage': 17_600_000.0,
            },
            tz='Asia/Ho_Chi_Minh',
        )
        cls.attendance_type = cls.env.ref('hr_work_entry.vn_work_entry_type_attendance')
        cls.overtime_type = cls.env.ref('hr_work_entry.vn_work_entry_type_overtime')
        cls.unpaid_type = cls.env.ref('hr_work_entry.vn_work_entry_type_unpaid_leave')
        cls.night = cls.env.ref('l10n_vn_hr_payroll.VN_PREMIUM_PAY_NIGHT')
        cls.weekly_rest = cls.env.ref('l10n_vn_hr_payroll.VN_PREMIUM_PAY_WEEKLY_REST')
        cls.public_holiday = cls.env.ref('l10n_vn_hr_payroll.VN_PREMIUM_PAY_PUBLIC_HOLIDAY')
        cls.rules = {rule.code: rule for rule in cls.structure.rule_ids}
        # The time rules classify the time entries on their own, see test_time_rules_classify_night_overtime
        cls.env['hr.time.rule'].search([]).write({'active': False})

    def _payslip(self, date_from, date_to, inputs=None):
        input_line_ids = [
            Command.create({'salary_rule_id': self.rules[code].id, 'amount': amount})
            for code, amount in (inputs or {}).items()
        ]
        return self._generate_payslip(date_from, date_to, input_line_ids=input_line_ids or False)

    def _create_overtime(self, day, hour_from, hour_to, options=None):
        return self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.overtime_type.id,
            'request_date_from': day,
            'request_date_to': day,
            'request_hour_from': hour_from,
            'request_hour_to': hour_to,
            'category_options_ids': [Command.set(options.ids)] if options else [],
        })

    def _line_total(self, payslip, code):
        return payslip._get_line_values([code])[code][payslip.id]['total']

    def test_basic_salary_below_personal_deduction(self):
        # 15m: 10.5% of employee contributions, no tax as the personal deduction is 15.5m
        self.version.wage = 15_000_000
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)
        self._validate_rule_computed(payslip, 'PIT_DEPENDANT_DEDUCTION', expected=False)
        self._validate_rule_computed(payslip, 'UNION_DUES', expected=False)

    def test_progressive_schedule_with_dependant(self):
        # 30m, 1 dependant: assessable 30m - 3.15m - 15.5m - 6.2m = 5.15m in the 5% band
        self.version.write({'wage': 30_000_000, 'l10n_vn_dependants': 1})
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)

    def test_insurance_ceiling_change_july_2026(self):
        # The social and health insurance ceiling follows the reference level: 20 x 2.34m until June
        # 2026, 20 x 2.53m from July 2026. The unemployment insurance ceiling (20 x 5.31m) is not hit.
        # June: 60m - 5.046m - 15.5m = 39.454m assessable in the 20% band (quick deduction 3.5m)
        self.version.wage = 60_000_000
        june = self._payslip(date(2026, 6, 1), date(2026, 6, 30))
        self._validate_payslip(june, label='june')
        july = self._payslip(date(2026, 7, 1), date(2026, 7, 31))
        self._validate_payslip(july, label='july')

    def test_unemployment_insurance_ceiling_per_zone(self):
        # 120m: social and health insurance capped at 46.8m, unemployment insurance at 20 x the
        # regional minimum wage of the zone (106.2m in zone I, 74m in zone IV)
        self.version.wage = 120_000_000
        zone_1 = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(zone_1, label='zone_1')
        self.version.l10n_vn_minimum_wage_region = '4'
        zone_4 = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(zone_4, label='zone_4')

    def test_contribution_wage_floor(self):
        # The contribution wage cannot be below the regional minimum wage of the zone (5.31m in
        # zone I in 2026), even for a part-time wage
        self.version.wage = 4_000_000
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)

    def test_overtime_and_night_work_premium_pays(self):
        # Overtime hours are paid at the rate of the premium pays carried by the time entry:
        # 2h on a normal day (150%), 4h on a Sunday (200%), 2h at night on a normal day
        # (150% + 30% night work + 20% x 150% additional). Hourly wage: 100,000.
        # From the 2026 tax period the whole overtime pay is exempt.
        self._create_overtime(date(2026, 3, 10), 17, 19)
        self._create_overtime(date(2026, 3, 15), 8, 12, options=self.weekly_rest)
        self._create_overtime(date(2026, 3, 17), 19, 21, options=self.night)
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_worked_days(payslip, {
            '002.00': (22, 176, 17_600_000),
            '040.00': (1, 8, 800_000),
        }, skip_lines=True)
        self._validate_payslip(payslip)

    def test_overtime_on_public_holiday(self):
        # 4h worked in the evening of a public holiday: 300%, on top of the pay of the holiday itself.
        # Time entries recorded during the scheduled hours of an absence day are not generated by
        # the calendar based work entries, hence the evening shift.
        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'calendar_id': self.resource_calendar.id,
            'company_id': self.env.company.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.vn_work_entry_type_public_holiday').id,
            # 12 March 2026, Asia/Ho_Chi_Minh (UTC+7)
            'date_from': datetime(2026, 3, 11, 17, 0),
            'date_to': datetime(2026, 3, 12, 16, 59, 59),
        })
        self._create_overtime(date(2026, 3, 12), 17, 21, options=self.public_holiday)
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_worked_days(payslip, {
            '002.00': (21, 168, 16_800_000),
            '006.00': (1, 8, 800_000),
            '040.00': (0.5, 4, 400_000),
        })
        self._validate_payslip(payslip)

    def test_overtime_exemption_before_2026(self):
        # Before the 2026 tax period only the premium above the normal hours wage is exempt:
        # 10h of overtime at 150% = 1.5m, of which 1m (the normal hours wage) is taxable, with the
        # 11m personal deduction and the seven bands schedule of 2025.
        # December 2025: 23 working days (184h), wage 18.4m for a 100,000 hourly wage.
        self.version.wage = 18_400_000
        self._create_overtime(date(2025, 12, 8), 17, 22)
        self._create_overtime(date(2025, 12, 9), 17, 22)
        december = self._payslip(date(2025, 12, 1), date(2025, 12, 31))
        self._validate_payslip(december, label='december_2025')
        # January 2026: 22 working days, the whole overtime pay is exempt
        self.version.wage = 17_600_000
        self._create_overtime(date(2026, 1, 12), 17, 22)
        self._create_overtime(date(2026, 1, 13), 17, 22)
        january = self._payslip(date(2026, 1, 1), date(2026, 1, 31))
        self._validate_payslip(january, label='january_2026')

    def test_no_contribution_with_14_unpaid_working_days(self):
        # 15 working days without pay: the wage is prorated and no contribution is due for the month
        self._generate_leave(self.employee, date(2026, 3, 2), date(2026, 3, 20), self.unpaid_type)
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(payslip._l10n_vn_get_unpaid_days(), 15)
        self._validate_payslip(payslip)

    def test_contribution_on_contract_wage_with_unpaid_days(self):
        # 10 working days without pay: the wage is prorated but the contributions are still due on
        # the full monthly wage of the labour contract
        self._generate_leave(self.employee, date(2026, 3, 2), date(2026, 3, 13), self.unpaid_type)
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(payslip._l10n_vn_get_unpaid_days(), 10)
        self._validate_payslip(payslip)

    def test_foreign_employee_without_unemployment_insurance(self):
        self.version.country_id = self.env.ref('base.us')
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)
        self._validate_rule_computed(payslip, 'UI_EMP', expected=False)
        self._validate_rule_computed(payslip, 'UI_EMPLR', expected=False)

    def test_insurance_exempt_employee(self):
        # Intra-corporate transferee: no compulsory insurance at all, taxed on the whole income
        self.version.l10n_vn_insurance_exempt = True
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)

    def test_non_resident_flat_rate(self):
        # 20% of the income, no deduction (the contributions still apply to an insured employee)
        self.version.write({'wage': 50_000_000, 'l10n_vn_pit_method': 'flat_non_resident'})
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)
        self._validate_rule_computed(payslip, 'PIT_PERSONAL_DEDUCTION', expected=False)

    def test_non_resident_overtime_is_taxable(self):
        self.version.l10n_vn_pit_method = 'flat_non_resident'
        self._create_overtime(date(2026, 3, 10), 17, 19)
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)

    def test_casual_withholding_threshold(self):
        # 10% on the payments of at least 2m (5m from July 2026), nothing below the threshold
        self.version.write({'l10n_vn_pit_method': 'flat_casual', 'l10n_vn_insurance_exempt': True})
        self.version.wage = 4_900_000
        june = self._payslip(date(2026, 6, 1), date(2026, 6, 30))
        self._validate_payslip(june, label='june_4_9m')
        july = self._payslip(date(2026, 7, 1), date(2026, 7, 31))
        self._validate_payslip(july, label='july_4_9m')
        self.version.wage = 5_100_000
        july = self._payslip(date(2026, 7, 1), date(2026, 7, 31))
        self._validate_payslip(july, label='july_5_1m')

    def test_meal_allowance_cap_change_july_2026(self):
        # 1.5m shift meal allowance: exempt up to 730,000 until June 2026, 1.2m from July 2026
        june = self._payslip(date(2026, 6, 1), date(2026, 6, 30), inputs={'MEAL_ALW': 1_500_000})
        self._validate_payslip(june, label='june')
        july = self._payslip(date(2026, 7, 1), date(2026, 7, 31), inputs={'MEAL_ALW': 1_500_000})
        self._validate_payslip(july, label='july')

    def test_housing_benefit_cap(self):
        # 10m of rent paid by the employer: taxable up to 15% of the 40m taxable income, not paid out
        # 46m - 4.2m - 15.5m = 26.3m assessable: 500,000 + 16.3m x 10%
        self.version.wage = 40_000_000
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31), inputs={'HOUSING_BENEFIT': 10_000_000})
        self._validate_payslip(payslip)

    def test_uniform_allowance_yearly_cap(self):
        # 5m exempt per year: 3m in March, then 3m in April of which 1m is taxable
        march = self._payslip(date(2026, 3, 1), date(2026, 3, 31), inputs={'UNIFORM_ALW': 3_000_000})
        self._validate_payslip(march, label='march')
        march.action_validate()
        april = self._payslip(date(2026, 4, 1), date(2026, 4, 30), inputs={'UNIFORM_ALW': 3_000_000})
        self._validate_payslip(april, label='april')

    def test_tet_bonus_taxed_in_the_month_of_payment(self):
        # 100m Tết bonus with a 15m wage in January 2026: the bonus is taxable but outside the
        # contribution wage, the assessable income (115m - 1.575m - 15.5m) reaches the 30% band
        self.version.wage = 15_000_000
        payslip = self._payslip(date(2026, 1, 1), date(2026, 1, 31), inputs={'TET_BONUS': 100_000_000})
        self._validate_payslip(payslip)

    def test_union_dues_capped(self):
        # 1% of the contribution wage, capped at 10% of the reference level (253,000 from July 2026)
        self.version.write({'wage': 40_000_000, 'l10n_vn_union_member': True})
        june = self._payslip(date(2026, 6, 1), date(2026, 6, 30))
        self._validate_payslip(june, label='june')
        july = self._payslip(date(2026, 7, 1), date(2026, 7, 31))
        self._validate_payslip(july, label='july')

    def test_company_payroll_configuration(self):
        # Reduced occupational accident rate and union funding rate approved for the employer
        config = self.env.company._get_payroll_config(date(2026, 3, 1))
        config.write({
            'l10n_vn_reduced_occupational_accident_rate': True,
            'l10n_vn_union_fund_rate': 1.6,
        })
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(payslip.payroll_config_id, config)
        self._validate_payslip(payslip)

    def test_net_salary_agreement_gross_up(self):
        # The employee takes home exactly the agreed 30m: the contributions and the tax are
        # grossed up. Fixed point: x = 10.5% x (30m + x) + 5% x (89.5% x (30m + x) - 27.9m)
        self.version.write({'wage': 30_000_000, 'l10n_vn_dependants': 2, 'l10n_vn_net_salary': True})
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)
        self.assertAlmostEqual(self._line_total(payslip, 'NET'), 30_000_000, delta=1)
        self.assertAlmostEqual(
            self._line_total(payslip, 'GROSS_UP'),
            -sum(self._line_total(payslip, code) for code in ('SI_EMP', 'HI_EMP', 'UI_EMP', 'PIT')),
            delta=1)

    def test_worked_example_september_2026(self):
        # Full month of September 2026, zone I, union member with one dependant:
        # 35m wage, 5m position allowance (contribution wage 40m), 1.5m meal allowance
        # (300,000 taxable), 1m fuel allowance (exempt), 10h of overtime on normal days
        # (10 x 35m / 176h x 150%, exempt). Assessable: 40.3m - 4.2m - 15.5m - 6.2m = 14.4m,
        # PIT 940,000, union dues capped at 253,000.
        self.version.write({
            'wage': 35_000_000,
            'l10n_vn_dependants': 1,
            'l10n_vn_union_member': True,
        })
        self.version._set_property_input_value('POSITION_ALW', 5_000_000)
        self.version._set_property_input_value('MEAL_ALW', 1_500_000)
        self.version._set_property_input_value('FUEL_ALW', 1_000_000)
        self._create_overtime(date(2026, 9, 8), 17, 22)
        self._create_overtime(date(2026, 9, 9), 17, 22)
        payslip = self._payslip(date(2026, 9, 1), date(2026, 9, 30))
        self._validate_payslip(payslip)

    def test_time_rules_classify_night_overtime(self):
        # Sunday 8 March 2026, 04:00 - 10:00: no schedule on Sunday, the whole attendance is
        # overtime on a weekly rest day, the 04:00 - 06:00 portion is also night work.
        # Monday 9 March 2026, 20:00 - 23:00 on top of the schedule: 22:00 - 23:00 is night work.
        self.env['hr.time.rule'].with_context(active_test=False).search([
            ('country_id', '=', self.env.ref('base.vn').id),
        ]).write({'active': True})
        for local_from, local_to in [
            (datetime(2026, 3, 8, 4), datetime(2026, 3, 8, 10)),
            (datetime(2026, 3, 9, 20), datetime(2026, 3, 9, 23)),
        ]:
            utc_offset = timedelta(hours=7)  # Asia/Ho_Chi_Minh
            self.env['hr.leave'].with_context(
                tracking_disable=True,
                mail_activity_automation_skip=True,
                leave_skip_date_check=True,
                leave_fast_create=True,
                leave_skip_state_check=True,
                leave_skip_date_from_to_computation=True,
            ).create({
                'employee_id': self.employee.id,
                'work_entry_type_id': self.attendance_type.id,
                'date_from': local_from - utc_offset,
                'date_to': local_to - utc_offset,
                'request_date_from': local_from.date(),
                'request_date_to': local_to.date(),
                'state': 'validate',
            })
        outputs = self.env['hr.leave'].search([('employee_id', '=', self.employee.id), ('time_rule_id', '!=', False)])
        hours_by_options = {
            frozenset(leave.category_options_ids.mapped('code')): (leave.date_to - leave.date_from).total_seconds() / 3600
            for leave in outputs
        }
        self.assertEqual(hours_by_options, {
            frozenset(['VN_PREMIUM_PAY_WEEKLY_REST', 'VN_PREMIUM_PAY_NIGHT']): 2.0,
            frozenset(['VN_PREMIUM_PAY_WEEKLY_REST']): 4.0,
            frozenset(['VN_PREMIUM_PAY_NIGHT']): 1.0,
        })
        # 176 scheduled hours + 3 hours on Monday evening at the normal rate, 6h of overtime at
        # 200%, 3h of night work at 30%, 2h of overtime at night at 20% x 200%
        payslip = self._payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip)
