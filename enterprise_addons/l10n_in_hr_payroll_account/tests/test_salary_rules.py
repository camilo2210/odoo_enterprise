# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
import datetime

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('in')
    def setUpClass(cls):
        super().setUpClass()
        cls.resource_calendar = cls.env['resource.calendar'].create({
            'name': 'IN Calendar',
            'company_id': cls.env.company.id,
            'full_time_required_hours': 40
        })
        cls._setup_common(
            country=cls.env.ref('base.in'),
            structure=cls.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary'),
            structure_type=cls.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp_pay'),
            resource_calendar=cls.resource_calendar
        )

    def test_regular_payslip_1(self):
        self.version.write({
            'wage': 32000,
            'l10n_in_provident_fund': True,
            'l10n_in_esic': True,
            'l10n_in_pt': True,
            'l10n_in_basic_percentage': 0.5,
            'l10n_in_hra_percentage': 0.5,
            'l10n_in_standard_allowance': 4167,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
            'l10n_in_performance_bonus_percentage': 0.0833,
            'l10n_in_leave_travel_percentage': 0.0833,
            'l10n_in_medical_insurance': 980.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_insured_first_children': True,
            'l10n_in_phone_subscription': 500.0,
            'l10n_in_internet_subscription': 300.0,
            'l10n_in_meal_voucher_amount': 1000.0,
            'l10n_in_company_transport': 200.0,
            'pt_rule_parameter_id': self.env.ref('l10n_in_hr_payroll.l10n_in_rule_parameter_pt_gujarat').id,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 16000.0, 'HRA': 8000.0, 'STD': 4167.0, 'P_BONUS': 1332.8, 'LTA': 1332.8, 'SPL': 1167.4, 'MOB': 500.0, 'INT': 300.0, 'MEAL': 1000.0, 'CAR': 200.0, 'GROSS': 34000.0, 'TDS': 0.0, 'PT': -200.0, 'PF': -1800.0, 'PFE': -1800.0, 'MED': -2940.0, 'NET': 27260.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_esic_threshold(self):
        self.version.write({
            'wage': 20000,
            'l10n_in_basic_percentage': 1.0,
            'l10n_in_hra_percentage': 0.0,
            'l10n_in_standard_allowance': 0.0,
            'l10n_in_performance_bonus_percentage': 0.0,
            'l10n_in_leave_travel_percentage': 0.0,
            'l10n_in_fixed_allowance_percentage': 0.0,
            'l10n_in_phone_subscription': 0.0,
            'l10n_in_internet_subscription': 0.0,
            'l10n_in_meal_voucher_amount': 0.0,
            'l10n_in_company_transport': 0.0,
            'l10n_in_medical_insurance': 0.0,
            'l10n_in_insured_spouse': False,
            'l10n_in_insured_first_children': False,
            'l10n_in_esic': True,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 20000.0, 'GROSS': 20000.0, 'TDS': 0.0, 'ESICS': -200.0, 'ESICF': -800.0, 'NET': 19000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_esic_above_threshold(self):
        self.version.write({
            'wage': 22000,
            'l10n_in_basic_percentage': 1.0,
            'l10n_in_hra_percentage': 0.0,
            'l10n_in_standard_allowance': 0.0,
            'l10n_in_performance_bonus_percentage': 0.0,
            'l10n_in_leave_travel_percentage': 0.0,
            'l10n_in_fixed_allowance_percentage': 0.0,
            'l10n_in_phone_subscription': 0.0,
            'l10n_in_internet_subscription': 0.0,
            'l10n_in_meal_voucher_amount': 0.0,
            'l10n_in_company_transport': 0.0,
            'l10n_in_medical_insurance': 0.0,
            'l10n_in_insured_spouse': False,
            'l10n_in_insured_first_children': False,
            'l10n_in_esic': True,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 22000.0, 'GROSS': 22000.0, 'TDS': 0.0, 'NET': 22000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_esic_pwd_below_extended_threshold(self):
        self.version.write({
            'wage': 24000,
            'l10n_in_basic_percentage': 1.0,
            'l10n_in_hra_percentage': 0.0,
            'l10n_in_standard_allowance': 0.0,
            'l10n_in_performance_bonus_percentage': 0.0,
            'l10n_in_leave_travel_percentage': 0.0,
            'l10n_in_fixed_allowance_percentage': 0.0,
            'l10n_in_phone_subscription': 0.0,
            'l10n_in_internet_subscription': 0.0,
            'l10n_in_meal_voucher_amount': 0.0,
            'l10n_in_company_transport': 0.0,
            'l10n_in_medical_insurance': 0.0,
            'l10n_in_insured_spouse': False,
            'l10n_in_insured_first_children': False,
            'l10n_in_esic': True,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
            'disabled': True,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 24000.0, 'GROSS': 24000.0, 'ESICS': -240.0, 'ESICF': -960.0, 'TDS': 0.0, 'NET': 22800.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_esic_pwd_above_extended_threshold(self):
        self.version.write({
            'wage': 26000,
            'l10n_in_basic_percentage': 1.0,
            'l10n_in_hra_percentage': 0.0,
            'l10n_in_standard_allowance': 0.0,
            'l10n_in_performance_bonus_percentage': 0.0,
            'l10n_in_leave_travel_percentage': 0.0,
            'l10n_in_fixed_allowance_percentage': 0.0,
            'l10n_in_phone_subscription': 0.0,
            'l10n_in_internet_subscription': 0.0,
            'l10n_in_meal_voucher_amount': 0.0,
            'l10n_in_company_transport': 0.0,
            'l10n_in_medical_insurance': 0.0,
            'l10n_in_insured_spouse': False,
            'l10n_in_insured_first_children': False,
            'l10n_in_esic': True,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
            'disabled': True,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 26000.0, 'GROSS': 26000.0, 'TDS': 0.0, 'NET': 26000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_2(self):
        self.version.company_id.write({
            'l10n_in_provident_fund': True,
            'l10n_in_pt': True,
        })
        self.version.write({
            'wage': 16000,
            'l10n_in_basic_percentage': 0.35,
            'l10n_in_hra_percentage': 0.4,
            'l10n_in_standard_allowance': 4167,
            'l10n_in_performance_bonus_percentage': 0.3,
            'l10n_in_leave_travel_percentage': 0.3,
            'l10n_in_medical_insurance': 560.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_gratuity_percentage': 0.0481,
            'sex': 'male',
            'pt_rule_parameter_id': self.env.ref('l10n_in_hr_payroll.l10n_in_rule_parameter_pt_maharashtra').id,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 5600.0, 'HRA': 2240.0, 'STD': 4167.0, 'P_BONUS': 1680.0, 'LTA': 1680.0, 'SPL': 633.0, 'GROSS': 16000.0, 'TDS': 0.0, 'PT': -200.0, 'PF': -672.0, 'PFE': -672.0, 'GRATUITY': -269.36, 'MED': -1120.0, 'NET': 13066.64}
        self._validate_payslip(payslip, payslip_results)
        self.version.sex = 'female'
        payslip.compute_sheet()
        payslip_results['PT'] = 0.0
        payslip_results['NET'] = 13266.64
        self._validate_payslip(payslip, payslip_results)

    def test_stipend_payslip_1(self):
        structure = self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_stipend')
        structure_type = self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern')
        self.version.write({
            'wage': 10000,
            'structure_type_id': structure_type.id,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31), struct_id=structure.id)
        payslip_results = {'GROSS': 10000.0, 'NET': 10000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_stipend_payslip_2(self):
        structure = self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_stipend')
        structure_type = self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern')
        self.version.write({
            'wage': 20000,
            'structure_type_id': structure_type.id,
        })
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31), struct_id=structure.id)
        payslip_results = {'GROSS': 20000.0, 'NET': 20000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_regular_payslip_with_public_holiday(self):
        self.version.write({
            'wage': 32000,
            'l10n_in_provident_fund': True,
            'l10n_in_esic': True,
            'l10n_in_pt': True,
            'l10n_in_basic_percentage': 0.5,
            'l10n_in_hra_percentage': 0.5,
            'l10n_in_standard_allowance': 4167,
            'l10n_in_esic_employee_percentage': 0.01,
            'l10n_in_esic_employer_percentage': 0.04,
            'l10n_in_performance_bonus_percentage': 0.0833,
            'l10n_in_leave_travel_percentage': 0.0833,
            'l10n_in_medical_insurance': 980.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_insured_first_children': True,
            'l10n_in_phone_subscription': 500.0,
            'l10n_in_internet_subscription': 300.0,
            'l10n_in_meal_voucher_amount': 1000.0,
            'l10n_in_company_transport': 200.0,
            'pt_rule_parameter_id': self.env.ref('l10n_in_hr_payroll.l10n_in_rule_parameter_pt_gujarat').id,
        })
        self.env['resource.calendar.leaves'].create([{
            'name': "Absence",
            'company_id': self.env.company.id,
            'resource_id': self.employee.resource_id.id,
            'date_from': datetime.datetime(2024, 1, 8, 6, 0, 0),
            'date_to': datetime.datetime(2024, 1, 9, 19, 0, 0),
            'count_as': "absence",
            'work_entry_type_id': self.env.ref('hr_work_entry.in_work_entry_type_unpaid_leave').id
        }])

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(len(payslip.worked_days_line_ids), 2)
        self.assertEqual(len(payslip.input_line_ids), 0)
        self.assertEqual(len(payslip.line_ids), 17)
        self._validate_worked_days(payslip, {
            '158.00': (1.0, 11.0, 0.0),
            '002.00': (22.0, 173.0, 30086.96),
        })
        payslip_results = {'BASIC': 15043.48, 'HRA': 7521.74, 'STD': 3917.89, 'P_BONUS': 1253.12, 'LTA': 1253.12, 'SPL': 1097.61, 'MOB': 500.0, 'INT': 300.0, 'MEAL': 1000.0, 'CAR': 200.0, 'GROSS': 32086.96, 'TDS': 0.0, 'PT': -200.0, 'PF': -1692.39, 'PFE': -1692.39, 'MED': -2940.0, 'NET': 25562.18}
        self._validate_payslip(payslip, payslip_results)

    def _setup_professional_tax_deduction_cycle(self):
        """Setup for professional tax deduction → monthly, quarterly, half-yearly, and yearly cycles"""
        self.version.l10n_in_lwf_deduction_cycle = 'half_yearly'
        self.version.pt_rule_parameter_id = self.env['hr.rule.parameter'].search([('code', '=', 'l10n_in_pt_gj')])
        self.version.wage = 15000
        self.version.l10n_in_basic_percentage = 1.0
        self.version.company_id.l10n_in_pt = True
        self.professional_tax_results = {'BASIC': 15000.0, 'GROSS': 15000.0, 'PT': -200.0, 'NET': 14800.0}
        self.no_professional_tax_results = {'BASIC': 15000.0, 'GROSS': 15000.0, 'NET': 15000}

    def test_professional_tax_deduction_half_yearly(self):
        self._setup_professional_tax_deduction_cycle()

        self.version.l10n_in_professional_tax_deduction_cycle = 'half_yearly'

        # June (due month) → should deduct (deduction for 2024's first half)
        payslip_june = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))
        self._validate_payslip(payslip_june, self.professional_tax_results, True)
        payslip_june.action_payslip_done()

        # Duplicate → should not deduct (2024's first half been deducted already, the second half's due has not been came yet)
        payslip_june_2 = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))
        self._validate_payslip(payslip_june_2, self.no_professional_tax_results, True)
        payslip_june_2.action_payslip_done()

        # Duplicate → already deducted in June (2024's first half been deducted already, the second half's due has not been came yet)
        payslip_august = self._generate_payslip(date(2024, 8, 1), date(2024, 8, 31))
        self._validate_payslip(payslip_august, self.no_professional_tax_results, True)
        payslip_august.action_payslip_done()

        # December (due month) → should deduct (tax deduction for 2024's second half)
        payslip_december = self._generate_payslip(date(2024, 12, 1), date(2024, 12, 31))
        self._validate_payslip(payslip_december, self.professional_tax_results, True)
        payslip_december.action_payslip_done()

        # deducted already in previous December (2025's first half deduction has not been arrived yet)
        payslip_february_2025 = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28))
        self._validate_payslip(payslip_february_2025, self.no_professional_tax_results, True)
        payslip_february_2025.action_payslip_done()

        # There was no deduction in June, this one should deduct (tax deduction for 2025's first half)
        payslip_july_2025 = self._generate_payslip(date(2025, 7, 1), date(2025, 7, 31))
        self._validate_payslip(payslip_july_2025, self.professional_tax_results, True)
        payslip_july_2025.action_payslip_done()

    def test_professional_tax_deduction_quarterly(self):
        self._setup_professional_tax_deduction_cycle()

        self.version.l10n_in_professional_tax_deduction_cycle = 'quarterly'

        # March (due month) → should be deducted (2024's first quarter deduction)
        payslip_march = self._generate_payslip(date(2024, 3, 1), date(2024, 3, 31))
        self._validate_payslip(payslip_march, self.professional_tax_results, True)
        payslip_march.action_payslip_done()

        # Shouldn't be deducted. Already paid in March (tax been already deducted for 2024's first quarter, not due for second quarter yet)
        payslip_may = self._generate_payslip(date(2024, 5, 1), date(2024, 5, 31))
        self._validate_payslip(payslip_may, self.no_professional_tax_results, True)
        payslip_may.action_payslip_done()

        # Did not deduct in June, it should be deducted for this one (deduction for 2024's second quarter)
        payslip_august = self._generate_payslip(date(2024, 8, 1), date(2024, 8, 31))
        self._validate_payslip(payslip_august, self.professional_tax_results, True)
        payslip_august.action_payslip_done()

        # September (due month) → should deduct (deduction for 2024's third quarter)
        payslip_september = self._generate_payslip(date(2024, 9, 1), date(2024, 9, 30))
        self._validate_payslip(payslip_september, self.professional_tax_results, True)
        payslip_september.action_payslip_done()

        # December (due month) → should deduct (deduction for 2025's fourth quarter)
        payslip_december = self._generate_payslip(date(2024, 12, 1), date(2024, 12, 31))
        self._validate_payslip(payslip_december, self.professional_tax_results, True)
        payslip_december.action_payslip_done()

    def test_professional_tax_deduction_monthly(self):
        self._setup_professional_tax_deduction_cycle()

        self.version.l10n_in_professional_tax_deduction_cycle = 'monthly'

        # Should deduct in each month
        payslip_february = self._generate_payslip(date(2024, 2, 1), date(2024, 2, 29))
        self._validate_payslip(payslip_february, self.professional_tax_results, True)
        payslip_february.action_payslip_done()

    def test_professional_tax_deduction_yearly(self):
        self._setup_professional_tax_deduction_cycle()

        self.version.l10n_in_professional_tax_deduction_cycle = 'yearly'

        # December (due month) → should be deducted (tax deduction for 2024)
        payslip_december = self._generate_payslip(date(2024, 12, 1), date(2024, 12, 31))
        self._validate_payslip(payslip_december, self.professional_tax_results, True)
        payslip_december.action_payslip_done()

        # Did not deduct in 2025-December (for year 2025 the tax has not been deducted yet), should be deducted
        payslip_january_2026 = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 31))
        self._validate_payslip(payslip_january_2026, self.professional_tax_results, True)
        payslip_january_2026.action_payslip_done()

        # 2025 is already done and 2026 due has not came yet
        payslip_march_2026 = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31))
        self._validate_payslip(payslip_march_2026, self.no_professional_tax_results, True)
        payslip_march_2026.action_payslip_done()

    def _setup_lwf(self, employee_contribution=25, employer_contribution=75):
        self.version.write({
            'wage': 50000,
            'l10n_in_basic_percentage': 1.0,
            'l10n_in_lwf_employee_contribution': employee_contribution,
            'l10n_in_lwf_employer_contribution': employer_contribution,
        })

    def test_lwf_deduction_cycles(self):
        """Test LWF deduction for half-yearly, monthly, and yearly cycles."""
        self._setup_lwf()
        lwf_results = {'BASIC': 50000.0, 'GROSS': 50000.0, 'LWFE': -25.0, 'LWF': -75.0, 'TDS': 0.0, 'NET': 49900.0}
        no_lwf_results = {'BASIC': 50000.0, 'GROSS': 50000.0, 'TDS': 0.0, 'NET': 50000.0}

        # --- Half-Yearly ---
        self.version.l10n_in_lwf_deduction_cycle = 'half_yearly'

        # June (due month) → should deduct
        payslip_june = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))
        self._validate_payslip(payslip_june, lwf_results)
        payslip_june.action_payslip_done()

        # Another June payslip → duplicate prevention
        payslip_june_2 = self._generate_payslip(date(2024, 6, 1), date(2024, 6, 30))
        self._validate_payslip(payslip_june_2, no_lwf_results)

        # July → non-due month, June already deducted
        payslip_july = self._generate_payslip(date(2024, 7, 1), date(2024, 7, 31))
        self._validate_payslip(payslip_july, no_lwf_results)

        # December (next due month) → should deduct
        payslip_dec = self._generate_payslip(date(2024, 12, 1), date(2024, 12, 31))
        self._validate_payslip(payslip_dec, lwf_results)
        payslip_dec.action_payslip_done()

        # June 2025 payslip not created → July should carry forward the deduction
        payslip_july_cf = self._generate_payslip(date(2025, 7, 1), date(2025, 7, 31))
        self._validate_payslip(payslip_july_cf, lwf_results)

        # --- Monthly ---
        self.version.l10n_in_lwf_deduction_cycle = 'monthly'

        payslip_jan = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        self._validate_payslip(payslip_jan, lwf_results)

        # --- Yearly ---
        self.version.l10n_in_lwf_deduction_cycle = 'yearly'

        # Create Dec 2025 payslip to satisfy the previous yearly due period
        payslip_dec_prev = self._generate_payslip(date(2025, 12, 1), date(2025, 12, 31))
        payslip_dec_prev.action_payslip_done()

        # June 2026 → not due for yearly
        payslip_june_yr = self._generate_payslip(date(2026, 6, 1), date(2026, 6, 30))
        self._validate_payslip(payslip_june_yr, no_lwf_results)

        # December 2026 → due for yearly
        payslip_dec_yr = self._generate_payslip(date(2026, 12, 1), date(2026, 12, 31))
        self._validate_payslip(payslip_dec_yr, lwf_results)

    def test_lwf_new_joiner_no_deduction_before_join(self):
        """Employee joining in July should not get June's half-yearly LWF deduction."""
        self._setup_lwf()
        self.version.l10n_in_lwf_deduction_cycle = 'half_yearly'
        self.employee.contract_date_start = date(2024, 7, 15)
        payslip_july = self._generate_payslip(date(2024, 7, 15), date(2024, 7, 31))
        payslip_results = {'BASIC': 50000.0, 'GROSS': 50000.0, 'TDS': 0.0, 'NET': 50000.0}
        self._validate_payslip(payslip_july, payslip_results)
