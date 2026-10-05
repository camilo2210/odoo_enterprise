# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta
from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('mx')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.mx'),
            structure=cls.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay'),
            structure_type=cls.env.ref('l10n_mx_hr_payroll.l10n_mx_employee'),
            version_fields={
                'wage': 50000.0,
                'contract_date_start': date(2021, 5, 31),
                'date_version': date(2021, 5, 31),
            },
        )

    def test_regular_payslip(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 50000.0, 'HOLIDAY_TO_SUB': 0.0, 'GROSS_WITHOUT_HOLIDAY': 50000.0, 'HOLIDAYS_ON_TIME': 0.0, 'GROSS': 50000.0, 'ISR': -9466.99, 'SBC_FIXED_SALARY': 1734.97, 'SBC_OTHER_EARNINGS': 0.0, 'SBC_COMMISSIONS': 0.0, 'SBC': 1734.97, 'RISK_IMSS_EMPLOYER': 268.92, 'DIS_FIX_IMSS_EMPLOYER': 656.05, 'DIS_ADD_IMSS_EMPLOYER': 485.5, 'DIS_ADD_IMSS_EMPLOYEE': -176.55, 'DIS_MED_IMSS_EMPLOYER': 564.73, 'DIS_MED_IMSS_EMPLOYEE': -201.69, 'DIS_MON_IMSS_EMPLOYER': 376.49, 'DIS_MON_IMSS_EMPLOYEE': -134.46, 'DIS_LIF_IMSS_EMPLOYER': 941.22, 'DIS_LIF_IMSS_EMPLOYEE': -336.15, 'RETIRE_IMSS_EMPLOYER': 1075.68, 'CEAV_IMSS_EMPLOYER': 2867.23, 'CEAV_IMSS_EMPLOYEE': -605.07, 'NURSERY_IMSS_EMPLOYER': 537.84, 'INFONAVIT_IMSS_EMPLOYER': 2689.21, 'IMSS_EMPLOYEE_TOTAL': 1453.92, 'IMSS_EMPLOYER_TOTAL': 10462.88, 'NET': 39079.09, 'PROVISIONS_CHRISTMAS_BONUS': 2117.49, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 2117.49, 'PROVISIONS_HOLIDAY_BONUS': 0.0, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 0.0, 'PROVISIONS_VACATIONS_BONUS': 17850.64, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 17850.64}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_paid_holiday(self):
        # 1/3 of the month is paid holidays
        self.env['hr.leave.allocation'].create({
            'name': 'Paid Time Off Allocation',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.mx_work_entry_type_legal_leave').id,
            'number_of_days': 20,
            'state': 'confirm',
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
        }).action_approve()
        self._generate_leave(self.employee, date(2024, 1, 1), date(2024, 1, 10), self.env.ref('hr_work_entry.mx_work_entry_type_legal_leave'))
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 50000.0, 'HOLIDAY_TO_SUB': 13333.33, 'GROSS_WITHOUT_HOLIDAY': 36666.67, 'HOLIDAYS_ON_TIME': 13333.33, 'GROSS': 50000.0, 'ISR': -9466.99, 'SBC_FIXED_SALARY': 1734.97, 'SBC_OTHER_EARNINGS': 0.0, 'SBC_COMMISSIONS': 0.0, 'SBC': 1734.97, 'RISK_IMSS_EMPLOYER': 268.92, 'DIS_FIX_IMSS_EMPLOYER': 656.05, 'DIS_ADD_IMSS_EMPLOYER': 485.5, 'DIS_ADD_IMSS_EMPLOYEE': -176.55, 'DIS_MED_IMSS_EMPLOYER': 564.73, 'DIS_MED_IMSS_EMPLOYEE': -201.69, 'DIS_MON_IMSS_EMPLOYER': 376.49, 'DIS_MON_IMSS_EMPLOYEE': -134.46, 'DIS_LIF_IMSS_EMPLOYER': 941.22, 'DIS_LIF_IMSS_EMPLOYEE': -336.15, 'RETIRE_IMSS_EMPLOYER': 1075.68, 'CEAV_IMSS_EMPLOYER': 2867.23, 'CEAV_IMSS_EMPLOYEE': -605.07, 'NURSERY_IMSS_EMPLOYER': 537.84, 'INFONAVIT_IMSS_EMPLOYER': 2689.21, 'IMSS_EMPLOYEE_TOTAL': 1453.92, 'IMSS_EMPLOYER_TOTAL': 10462.88, 'NET': 39079.09, 'PROVISIONS_CHRISTMAS_BONUS': 2117.49, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 2117.49, 'PROVISIONS_HOLIDAY_BONUS': 0.0, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 0.0, 'PROVISIONS_VACATIONS_BONUS': 17850.64, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 17850.64}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_complete_case(self):
        self.version.write({
            'schedule_pay': 'bi-weekly',
            'l10n_mx_meal_voucher_amount': 3000,
            'l10n_mx_transport_amount': 2000,
            'l10n_mx_gasoline_amount': 1000,
            'l10n_mx_savings_fund': 4000,
            'l10n_mx_holiday_bonus_rate': 0.25,
        })
        payslip = self._generate_payslip(date(2024, 9, 16), date(2024, 9, 30))
        payslip_results = {'BASIC': 50000.0, 'HOLIDAY_TO_SUB': 0.0, 'GROSS_WITHOUT_HOLIDAY': 50000.0, 'HOLIDAYS_ON_TIME': 0.0, 'ANNUAL_SOCIAL_PROVISION': 277244.52, 'EXEMPTION_SOCIAL_SECURITY': 3300.53, 'GAS_PERIOD': 1000.0, 'TRANSPORT_PERIOD': 2000.0, 'MEAL_VOUCHER_PERIOD': 3000.0, 'NO_TAX_GAS': 550.09, 'NO_TAX_TRANSPORT': 1100.18, 'NO_TAX_MEAL_VOUCHER': 1650.27, 'TAX_GAS': 449.91, 'TAX_TRANSPORT': 899.82, 'TAX_MEAL_VOUCH': 1349.74, 'SAVINGS_FUND_SALARY_LIMIT': 6500.0, 'SAVINGS_FUND_LIMIT_UMA': 2145.34, 'SAVINGS_FUND_EMPLOYER_ALW': 2000.0, 'GROSS': 52699.47, 'ISR': -13206.11, 'SAVINGS_FUND_EMPLOYEE': -2000.0, 'SAVINGS_FUND_EMPLOYER_DED': -2000.0, 'SBC_FIXED_SALARY': 3510.93, 'SBC_OTHER_EARNINGS': 0.0, 'SBC_COMMISSIONS': 0.0, 'SBC': 2714.25, 'RISK_IMSS_EMPLOYER': 203.57, 'DIS_FIX_IMSS_EMPLOYER': 332.22, 'DIS_ADD_IMSS_EMPLOYER': 394.11, 'DIS_ADD_IMSS_EMPLOYEE': -143.31, 'DIS_MED_IMSS_EMPLOYER': 427.49, 'DIS_MED_IMSS_EMPLOYEE': -152.68, 'DIS_MON_IMSS_EMPLOYER': 285.0, 'DIS_MON_IMSS_EMPLOYEE': -101.78, 'DIS_LIF_IMSS_EMPLOYER': 712.49, 'DIS_LIF_IMSS_EMPLOYEE': -254.46, 'RETIRE_IMSS_EMPLOYER': 814.28, 'CEAV_IMSS_EMPLOYER': 2170.45, 'CEAV_IMSS_EMPLOYEE': -458.03, 'NURSERY_IMSS_EMPLOYER': 407.14, 'INFONAVIT_IMSS_EMPLOYER': 2035.69, 'IMSS_EMPLOYEE_TOTAL': 1110.26, 'IMSS_EMPLOYER_TOTAL': 7782.43, 'NET': 39683.63, 'PROVISIONS_CHRISTMAS_BONUS': 37431.69, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 37431.69, 'PROVISIONS_HOLIDAY_BONUS': 5000.0, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 5000.0, 'PROVISIONS_VACATIONS_BONUS': 20000.0, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 20000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_minimum_wage(self):
        self.version.wage = 8364.0
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'BASIC': 8364.0, 'HOLIDAY_TO_SUB': 0.0, 'GROSS_WITHOUT_HOLIDAY': 8364.0, 'HOLIDAYS_ON_TIME': 0.0, 'GROSS': 8364, 'ISR': 0.0, 'ISR_MINIMUM_WAGE': 592.91, 'SUBSIDY_CURRENT_MONTH': 0.0, 'SBC_FIXED_SALARY': 290.26, 'SBC_COMMISSIONS': 0.0, 'SBC_OTHER_EARNINGS': 0.0, 'SBC': 290.26, 'RISK_IMSS_EMPLOYER': 44.99, 'DIS_FIX_IMSS_EMPLOYER': 686.6, 'DIS_ADD_IMSS_EMPLOYER': 0.0, 'DIS_ADD_IMSS_EMPLOYEE': 0.0, 'DIS_MED_IMSS_EMPLOYER': 94.48, 'DIS_MED_IMSS_EMPLOYEE': -33.74, 'DIS_MON_IMSS_EMPLOYER': 62.99, 'DIS_MON_IMSS_EMPLOYEE': -22.49, 'DIS_LIF_IMSS_EMPLOYER': 157.46, 'DIS_LIF_IMSS_EMPLOYEE': -56.24, 'RETIRE_IMSS_EMPLOYER': 179.96, 'CEAV_IMSS_EMPLOYER': 477.52, 'CEAV_IMSS_EMPLOYEE': -101.23, 'NURSERY_IMSS_EMPLOYER': 89.98, 'INFONAVIT_IMSS_EMPLOYER': 449.9, 'IMSS_MINIMUM_WAGE': 213.7, 'IMSS_EMPLOYEE_TOTAL': 0.0, 'IMSS_EMPLOYER_TOTAL': 2243.88, 'NET': 8364.0, 'PROVISIONS_CHRISTMAS_BONUS': 355.18, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 355.18, 'PROVISIONS_HOLIDAY_BONUS': 0.0, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 0.0, 'PROVISIONS_VACATIONS_BONUS': 3368.52, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 3368.52}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_minimum_wage_with_commissions(self):
        self.version.wage = 8364.0
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip._set_input_value('COMMISSIONS', 1000.0)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 8364.0, 'HOLIDAY_TO_SUB': 0.0, 'GROSS_WITHOUT_HOLIDAY': 8364.0, 'HOLIDAYS_ON_TIME': 0.0, 'COMMISSIONS': 1000.0, 'GROSS': 9364.0, 'ISR': -701.71, 'SUBSIDY_CURRENT_MONTH': 474.95, 'SUBSIDY': 474.95, 'SBC_FIXED_SALARY': 290.26, 'SBC_COMMISSIONS': 0.0, 'SBC_OTHER_EARNINGS': 0.0, 'SBC': 290.26, 'RISK_IMSS_EMPLOYER': 44.99, 'DIS_FIX_IMSS_EMPLOYER': 686.6, 'DIS_ADD_IMSS_EMPLOYER': 0.0, 'DIS_ADD_IMSS_EMPLOYEE': 0.0, 'DIS_MED_IMSS_EMPLOYER': 94.48, 'DIS_MED_IMSS_EMPLOYEE': -33.74, 'DIS_MON_IMSS_EMPLOYER': 62.99, 'DIS_MON_IMSS_EMPLOYEE': -22.49, 'DIS_LIF_IMSS_EMPLOYER': 157.46, 'DIS_LIF_IMSS_EMPLOYEE': -56.24, 'RETIRE_IMSS_EMPLOYER': 179.96, 'CEAV_IMSS_EMPLOYER': 477.52, 'CEAV_IMSS_EMPLOYEE': -101.23, 'NURSERY_IMSS_EMPLOYER': 89.98, 'INFONAVIT_IMSS_EMPLOYER': 449.9, 'IMSS_EMPLOYEE_TOTAL': 0.0, 'IMSS_EMPLOYER_TOTAL': 2243.88, 'IMSS_MINIMUM_WAGE': 213.7, 'NET': 9137.24, 'PROVISIONS_CHRISTMAS_BONUS': 355.18, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 355.18, 'PROVISIONS_HOLIDAY_BONUS': 0.0, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 0.0, 'PROVISIONS_VACATIONS_BONUS': 3368.52, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 3368.52}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_just_over_minimum_wage_with_leaves(self):
        self.version.write({
            'wage': 8364.1,
            'resource_calendar_id': self.env.ref('l10n_mx_hr_payroll.resource_calendar_def_48h').id,
        })

        self._generate_leave(self.employee, date(2025, 1, 10), date(2025, 1, 10), self.env.ref('hr_work_entry.mx_work_entry_type_unpaid_leave'))
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'BASIC': 8085.3, 'HOLIDAY_TO_SUB': 0.0, 'DIS_ABSENCE': -278.8, 'GROSS_WITHOUT_HOLIDAY': 8364.1, 'HOLIDAYS_ON_TIME': 0.0, 'GROSS': 8085.3, 'ISR': -562.58, 'SUBSIDY_CURRENT_MONTH': 474.95, 'SUBSIDY': 474.95, 'SBC_FIXED_SALARY': 290.26, 'SBC_OTHER_EARNINGS': 0.0, 'SBC_COMMISSIONS': 0.0, 'SBC': 290.26, 'RISK_IMSS_EMPLOYER': 43.54, 'DIS_FIX_IMSS_EMPLOYER': 686.6, 'DIS_ADD_IMSS_EMPLOYER': 0.0, 'DIS_ADD_IMSS_EMPLOYEE': 0.0, 'DIS_MED_IMSS_EMPLOYER': 94.48, 'DIS_MED_IMSS_EMPLOYEE': -33.74, 'DIS_MON_IMSS_EMPLOYER': 62.99, 'DIS_MON_IMSS_EMPLOYEE': -22.5, 'DIS_LIF_IMSS_EMPLOYER': 152.39, 'DIS_LIF_IMSS_EMPLOYEE': -54.42, 'RETIRE_IMSS_EMPLOYER': 174.16, 'CEAV_IMSS_EMPLOYER': 462.12, 'CEAV_IMSS_EMPLOYEE': -97.96, 'NURSERY_IMSS_EMPLOYER': 87.08, 'INFONAVIT_IMSS_EMPLOYER': 435.39, 'IMSS_EMPLOYEE_TOTAL': 208.63, 'IMSS_EMPLOYER_TOTAL': 2198.74, 'NET': 7789.04, 'PROVISIONS_CHRISTMAS_BONUS': 355.19, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 355.19, 'PROVISIONS_HOLIDAY_BONUS': 0.0, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 0.0, 'PROVISIONS_VACATIONS_BONUS': 3368.56, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 3368.56}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_holiday_bonus(self):
        self.version.write({
            'contract_date_start': date(2025, 7, 1),
            'l10n_mx_holiday_bonus_rate': 0.25,
        })
        payslip = self._generate_payslip(date(2026, 7, 1), date(2026, 7, 31))
        payslip_results = {'BASIC': 50000.0, 'HOLIDAY_TO_SUB': 0.0, 'GROSS_WITHOUT_HOLIDAY': 50000.0, 'HOLIDAYS_ON_TIME': 0.0, 'NO_TAX_HOLIDAY_BONUS': 1759.65, 'TAX_HOLIDAY_BONUS': 3240.35, 'GROSS': 50000.0, 'ISR': -9107.82, 'ISR_HOLIDAY_TAX': -762.13, 'SBC_FIXED_SALARY': 1751.14, 'SBC_COMMISSIONS': 0.0, 'SBC_OTHER_EARNINGS': 0.0, 'SBC': 1751.14, 'RISK_IMSS_EMPLOYER': 271.43, 'DIS_FIX_IMSS_EMPLOYER': 741.87, 'DIS_ADD_IMSS_EMPLOYER': 477.13, 'DIS_ADD_IMSS_EMPLOYEE': -173.5, 'DIS_MED_IMSS_EMPLOYER': 570.0, 'DIS_MED_IMSS_EMPLOYEE': -203.57, 'DIS_MON_IMSS_EMPLOYER': 380.0, 'DIS_MON_IMSS_EMPLOYEE': -135.71, 'DIS_LIF_IMSS_EMPLOYER': 949.99, 'DIS_LIF_IMSS_EMPLOYEE': -339.28, 'RETIRE_IMSS_EMPLOYER': 1085.71, 'CEAV_IMSS_EMPLOYER': 4078.46, 'CEAV_IMSS_EMPLOYEE': -610.71, 'NURSERY_IMSS_EMPLOYER': 542.85, 'INFONAVIT_IMSS_EMPLOYER': 2714.27, 'IMSS_EMPLOYEE_TOTAL': 1462.78, 'IMSS_EMPLOYER_TOTAL': 11811.71, 'NET': 43667.27, 'PROVISIONS_CHRISTMAS_BONUS': 14520.55, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 14520.55, 'PROVISIONS_HOLIDAY_BONUS': 479.45, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 479.45, 'PROVISIONS_VACATIONS_BONUS': 1917.81, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 1917.81}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_SBC_calculation(self):
        self.employee.contract_date_end = date(2026, 5, 25)
        new_version = self.employee.create_contract(date=date(2026, 6, 5))

        self._generate_leave(self.employee, date(2026, 5, 12), date(2026, 5, 12), self.env.ref('hr_work_entry.mx_work_entry_type_unpaid_leave'))
        self._generate_leave(self.employee, date(2026, 6, 12), date(2026, 6, 12), self.env.ref('hr_work_entry.l10n_mx_work_entry_type_work_risk_imss'))

        payslip_may_commissions = self._generate_payslip(date(2026, 5, 1), date(2026, 5, 31))
        payslip_may_commissions._set_input_value('COMMISSIONS', 6000.0)
        payslip_may_commissions.compute_sheet()
        payslip_may_commissions.action_validate()

        payslip_june_bonus = self._generate_payslip(date(2026, 6, 1), date(2026, 6, 30), version_id=new_version.id)
        payslip_june_bonus._set_input_value('BONUS', 6000.0)
        payslip_june_bonus.compute_sheet()
        payslip_june_bonus.action_validate()

        payslip_july_sbc = self._generate_payslip(date(2026, 7, 1), date(2026, 7, 31), version_id=new_version.id)
        payslip_july_sbc.compute_sheet()

        payslip_results = {'BASIC': 50000.0, 'HOLIDAY_TO_SUB': 0.0, 'GROSS_WITHOUT_HOLIDAY': 50000.0, 'HOLIDAYS_ON_TIME': 0.0, 'GROSS': 50000.0, 'ISR': -9107.82, 'SBC_FIXED_SALARY': 1735.16, 'SBC_COMMISSIONS': 122.45, 'SBC_OTHER_EARNINGS': 122.45, 'SBC': 1980.06, 'RISK_IMSS_EMPLOYER': 306.91, 'DIS_FIX_IMSS_EMPLOYER': 741.87, 'DIS_ADD_IMSS_EMPLOYER': 555.19, 'DIS_ADD_IMSS_EMPLOYEE': -201.89, 'DIS_MED_IMSS_EMPLOYER': 644.51, 'DIS_MED_IMSS_EMPLOYEE': -230.18, 'DIS_MON_IMSS_EMPLOYER': 429.67, 'DIS_MON_IMSS_EMPLOYEE': -153.45, 'DIS_LIF_IMSS_EMPLOYER': 1074.18, 'DIS_LIF_IMSS_EMPLOYEE': -383.64, 'RETIRE_IMSS_EMPLOYER': 1227.64, 'CEAV_IMSS_EMPLOYER': 4611.61, 'CEAV_IMSS_EMPLOYEE': -690.55, 'NURSERY_IMSS_EMPLOYER': 613.82, 'INFONAVIT_IMSS_EMPLOYER': 3069.09, 'IMSS_EMPLOYEE_TOTAL': 1659.71, 'IMSS_EMPLOYER_TOTAL': 13274.49, 'NET': 39232.47, 'PROVISIONS_CHRISTMAS_BONUS': 14383.56, 'PERIOD_PROVISIONS_CHRISTMAS_BONUS': 2054.79, 'PROVISIONS_HOLIDAY_BONUS': 0.0, 'PERIOD_PROVISIONS_HOLIDAY_BONUS': 0.0, 'PROVISIONS_VACATIONS_BONUS': 3068.49, 'PERIOD_PROVISIONS_VACATIONS_BONUS': 557.07}
        self._validate_payslip(payslip_july_sbc, payslip_results)

    def test_10_christmas_bonus_1(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 12, 31), self.env.ref('l10n_mx_hr_payroll.l10n_mx_christmas_bonus').id)
        payslip_results = {'BASIC': 25000.0, 'EXEMPT': 1628.55, 'GROSS': 23371.45, 'ISR': -7011.44, 'NET': 17988.57}
        self._validate_payslip(payslip, payslip_results)

    def test_10_christmas_bonus_2(self):
        self.employee.version_id.l10n_mx_christmas_bonus = 30.0
        self._generate_leave(self.employee, date(2024, 1, 1), date(2024, 1, 10), self.env.ref('hr_work_entry.mx_work_entry_type_unpaid_leave'))
        self._generate_leave(self.employee, date(2024, 2, 5), date(2024, 2, 7), self.env.ref('hr_work_entry.l10n_mx_work_entry_type_work_risk_imss'))
        self._generate_leave(self.employee, date(2024, 3, 4), date(2024, 3, 6), self.env.ref('hr_work_entry.l10n_mx_work_entry_type_maternity_imss'))
        self._generate_leave(self.employee, date(2024, 4, 1), date(2024, 4, 3), self.env.ref('hr_work_entry.l10n_mx_work_entry_type_disability_due_to_illness_imss'))

        last_christmas_provision = 0
        for i in range(12):
            monthly_payslip = self._generate_payslip(date(2024, i+1, 1), date(2024, i+1, 1) + relativedelta(months=1, days=-1))
            monthly_payslip.action_payslip_done()

            last_christmas_provision = monthly_payslip._get_line_values(['PROVISIONS_CHRISTMAS_BONUS'], compute_sum=True)['PROVISIONS_CHRISTMAS_BONUS']['sum']['total']

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 12, 31), self.env.ref('l10n_mx_hr_payroll.l10n_mx_christmas_bonus').id)
        payslip_results = {'BASIC': 47677.6, 'EXEMPT': 1628.55, 'GROSS': 46049.05, 'ISR': -13814.71, 'NET': 33862.88}
        self._validate_payslip(payslip, payslip_results)

        christmas_bonus = payslip._get_line_values(['BASIC'], compute_sum=True)['BASIC']['sum']['total']
        self.assertEqual(last_christmas_provision, christmas_bonus)

    def test_10_christmas_bonus_3(self):
        self.employee.version_id.l10n_mx_christmas_bonus = 30.0
        self._generate_leave(self.employee, date(2024, 1, 2), date(2024, 1, 2), self.env.ref('hr_work_entry.mx_work_entry_type_unpaid_leave'))
        self._generate_leave(self.employee, date(2024, 1, 3), date(2024, 1, 3), self.env.ref('hr_work_entry.l10n_mx_work_entry_type_work_risk_imss'))
        self._generate_leave(self.employee, date(2024, 1, 4), date(2024, 1, 4), self.env.ref('hr_work_entry.l10n_mx_work_entry_type_maternity_imss'))
        self._generate_leave(self.employee, date(2024, 1, 5), date(2024, 1, 5), self.env.ref('hr_work_entry.l10n_mx_work_entry_type_disability_due_to_illness_imss'))

        last_christmas_provision = 0
        for i in range(12):
            monthly_payslip = self._generate_payslip(date(2024, i+1, 1), date(2024, i+1, 1) + relativedelta(months=1, days=-1))
            monthly_payslip.action_payslip_done()

            last_christmas_provision = monthly_payslip._get_line_values(['PROVISIONS_CHRISTMAS_BONUS'], compute_sum=True)['PROVISIONS_CHRISTMAS_BONUS']['sum']['total']

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 12, 31), self.env.ref('l10n_mx_hr_payroll.l10n_mx_christmas_bonus').id)
        payslip_results = {'BASIC': 49453.55, 'EXEMPT': 1628.55, 'GROSS': 47825.0, 'ISR': -14347.5, 'NET': 35106.05}
        self._validate_payslip(payslip, payslip_results)

        christmas_bonus = payslip._get_line_values(['BASIC'], compute_sum=True)['BASIC']['sum']['total']
        self.assertEqual(last_christmas_provision, christmas_bonus)

    def test_10_christmas_bonus_4(self):
        self.version.contract_date_start = date(2024, 6, 18)
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 12, 31), self.env.ref('l10n_mx_hr_payroll.l10n_mx_christmas_bonus').id)
        payslip_results = {'BASIC': 13456.28, 'EXEMPT': 1628.55, 'GROSS': 11827.73, 'ISR': -3548.32, 'NET': 9907.96}
        self._validate_payslip(payslip, payslip_results)

    def test_weekly_schedule_pay_no_code(self):
        structure = self.env['hr.payroll.structure'].create({
            'name': 'Test Structure',
            'country_id': self.env.ref('base.mx').id,
            'type_id': self.env.ref('l10n_mx_hr_payroll.l10n_mx_employee').id,
            'report_id': self.env.ref('l10n_mx_hr_payroll.action_report_payslip_mx').id,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31), struct_id=structure.id)
        payslip_results = {'BASIC': 50000.0, 'GROSS': 50000.0, 'NET': 50000.0}
        self._validate_payslip(payslip, payslip_results)
