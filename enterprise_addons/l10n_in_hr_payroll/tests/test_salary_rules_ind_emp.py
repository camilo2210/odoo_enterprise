# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll.tests.common import TestPayrollBase


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidationIndEmp(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.in'),
            structure=cls.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary'),
            structure_type=cls.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp_pay'),
        )

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
        payslip_results = {'BASIC': 20000.0, 'GROSS': 20000.0, 'ESICS': -200.0, 'ESICF': -800.0, 'TDS': 0.0, 'NET': 19000.0}
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
