# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('bd')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.bd'),
            structure=cls.env.ref('l10n_bd_hr_payroll.hr_payroll_structure_bd_employee_salary'),
            structure_type=cls.env.ref('l10n_bd_hr_payroll.structure_type_employee_bd'),
            employee_fields={
                'sex': 'male',
            },
            resource_calendar=cls.env.ref('l10n_bd_hr_payroll.resource_calendar_def_40h'),
        )

    def test_male_payslip_1(self):
        self.version.wage = 40000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'GROSS': 40000.0, 'TAXABLE_AMOUNT': 26666.67, 'TAXES': -416.67, 'NET': 39583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_male_payslip_2(self):
        self.version.wage = 60000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 60000.0, 'GROSS': 60000.0, 'TAXABLE_AMOUNT': 40000.0, 'TAXES': -666.67, 'NET': 59333.33}
        self._validate_payslip(payslip, payslip_results)

    def test_male_payslip_3(self):
        self.version.wage = 80000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 80000.0, 'GROSS': 80000.0, 'TAXABLE_AMOUNT': 53333.33, 'TAXES': -2000.0, 'NET': 78000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_female_payslip_1(self):
        self.employee.sex = 'female'
        self.version.wage = 40000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'GROSS': 40000.0, 'TAXABLE_AMOUNT': 26666.67, 'TAXES': -416.67, 'NET': 39583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_female_payslip_2(self):
        self.employee.sex = 'female'
        self.version.wage = 60000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 60000.0, 'GROSS': 60000.0, 'TAXABLE_AMOUNT': 40000.0, 'TAXES': -416.67, 'NET': 59583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_female_payslip_3(self):
        self.employee.sex = 'female'
        self.version.wage = 80000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 80000.0, 'GROSS': 80000.0, 'TAXABLE_AMOUNT': 53333.33, 'TAXES': -1583.33, 'NET': 78416.67}
        self._validate_payslip(payslip, payslip_results)

    def test_disabled_payslip_1(self):
        self.employee.disabled = True
        self.version.wage = 40000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'GROSS': 40000.0, 'TAXABLE_AMOUNT': 26666.67, 'TAXES': -416.67, 'NET': 39583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_disabled_payslip_2(self):
        self.employee.disabled = True
        self.version.wage = 60000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 60000.0, 'GROSS': 60000.0, 'TAXABLE_AMOUNT': 40000.0, 'TAXES': -416.67, 'NET': 59583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_disabled_payslip_3(self):
        self.employee.disabled = True
        self.version.wage = 80000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 80000.0, 'GROSS': 80000.0, 'TAXABLE_AMOUNT': 53333.33, 'TAXES': -958.33, 'NET': 79041.67}
        self._validate_payslip(payslip, payslip_results)

    def test_gazetted_freedom_fighter_payslip_1(self):
        gazetted_war_rule = self.env.ref('l10n_bd_hr_payroll.l10n_bd_income_tax_gazetted_war_founded_freedom_fighter_deduction')
        self.employee.payroll_properties = {
            gazetted_war_rule.code: True,
        }
        self.version.wage = 40000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'GROSS': 40000.0, 'TAXABLE_AMOUNT': 26666.67, 'GWARDEDUCTION': 500000.0, 'TAXES': -416.67, 'NET': 39583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_gazetted_freedom_fighter_payslip_2(self):
        gazetted_war_rule = self.env.ref('l10n_bd_hr_payroll.l10n_bd_income_tax_gazetted_war_founded_freedom_fighter_deduction')
        self.employee.payroll_properties = {
            gazetted_war_rule.code: True,
        }
        self.version.wage = 60000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 60000.0, 'GROSS': 60000.0, 'TAXABLE_AMOUNT': 40000.0, 'GWARDEDUCTION': 500000.0, 'TAXES': -416.67, 'NET': 59583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_gazetted_freedom_fighter_payslip_3(self):
        gazetted_war_rule = self.env.ref('l10n_bd_hr_payroll.l10n_bd_income_tax_gazetted_war_founded_freedom_fighter_deduction')
        self.employee.payroll_properties = {
            gazetted_war_rule.code: True,
        }
        self.version.wage = 80000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 80000.0, 'GROSS': 80000.0, 'TAXABLE_AMOUNT': 53333.33, 'GWARDEDUCTION': 500000.0, 'TAXES': -750.0, 'NET': 79250.0}
        self._validate_payslip(payslip, payslip_results)

    def test_senior_payslip_1(self):
        self.employee.birthday = date(1950, 1, 1)
        self.version.wage = 40000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'GROSS': 40000.0, 'TAXABLE_AMOUNT': 26666.67, 'TAXES': -416.67, 'NET': 39583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_senior_payslip_2(self):
        self.employee.birthday = date(1950, 1, 1)
        self.version.wage = 60000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 60000.0, 'GROSS': 60000.0, 'TAXABLE_AMOUNT': 40000.0, 'TAXES': -416.67, 'NET': 59583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_senior_payslip_3(self):
        self.employee.birthday = date(1950, 1, 1)
        self.version.wage = 80000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 80000.0, 'GROSS': 80000.0, 'TAXABLE_AMOUNT': 53333.33, 'TAXES': -1583.33, 'NET': 78416.67}
        self._validate_payslip(payslip, payslip_results)

    def test_disabled_dependent_payslip_1(self):
        disabled_dependent_rule = self.env.ref('l10n_bd_hr_payroll.l10n_bd_income_tax_disabled_dependent_deduction')
        self.employee.payroll_properties = {
            disabled_dependent_rule.code: 5,
        }
        self.version.wage = 40000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'GROSS': 40000.0, 'TAXABLE_AMOUNT': 26666.67, 'DISABLEDDEDUCTION': 250000.0, 'TAXES': -416.67, 'NET': 39583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_disabled_dependent_payslip_2(self):
        disabled_dependent_rule = self.env.ref('l10n_bd_hr_payroll.l10n_bd_income_tax_disabled_dependent_deduction')
        self.employee.payroll_properties = {
            disabled_dependent_rule.code: 5,
        }
        self.version.wage = 60000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 60000.0, 'GROSS': 60000.0, 'TAXABLE_AMOUNT': 40000.0, 'DISABLEDDEDUCTION': 250000.0, 'TAXES': -416.67, 'NET': 59583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_disabled_dependent_payslip_3(self):
        disabled_dependent_rule = self.env.ref('l10n_bd_hr_payroll.l10n_bd_income_tax_disabled_dependent_deduction')
        self.employee.payroll_properties = {
            disabled_dependent_rule.code: 5,
        }
        self.version.wage = 80000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 80000.0, 'GROSS': 80000.0, 'TAXABLE_AMOUNT': 53333.33, 'DISABLEDDEDUCTION': 250000.0, 'TAXES': -416.67, 'NET': 79583.33}
        self._validate_payslip(payslip, payslip_results)

    def test_other_inputs_payslip_1(self):
        self.version.wage = 40000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip._set_input_values({
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_other_allowances_rule').code: 2000,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_salary_arrears_rule').code: 3000,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_over_time_rule').code: 500,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_prov_fund_rule').code: 400,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_grat_fund_rule').code: 300,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_tax_exemption_rule').code: 100,
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 40000.0, 'EXTRA_HOURS': 500.0, 'GRAT_FUND': 300.0, 'OTHER_ALLOW': 2000.0, 'PROV_FUND': 400.0, 'SALARY_ARREARS': 3000.0, 'GROSS': 46200.0, 'TAX_CREDITS': 100.0, 'TAXABLE_AMOUNT': 30700.0, 'TAXES': -416.67, 'NET': 45783.33}
        self._validate_payslip(payslip, payslip_results)

    def test_other_inputs_payslip_2(self):
        self.version.wage = 60000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip._set_input_values({
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_other_allowances_rule').code: 2000,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_salary_arrears_rule').code: 3000,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_over_time_rule').code: 500,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_prov_fund_rule').code: 400,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_grat_fund_rule').code: 300,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_tax_exemption_rule').code: 100,
        })
        payslip.compute_sheet()

        payslip_results = {'BASIC': 60000.0, 'EXTRA_HOURS': 500.0, 'GRAT_FUND': 300.0, 'OTHER_ALLOW': 2000.0, 'PROV_FUND': 400.0, 'SALARY_ARREARS': 3000.0, 'GROSS': 66200.0, 'TAX_CREDITS': 100.0, 'TAXABLE_AMOUNT': 44033.33, 'TAXES': -1070.0, 'NET': 65130.0}
        self._validate_payslip(payslip, payslip_results)

    def test_other_inputs_payslip_3(self):
        self.version.wage = 80000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip._set_input_values({
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_other_allowances_rule').code: 2000,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_salary_arrears_rule').code: 3000,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_over_time_rule').code: 500,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_prov_fund_rule').code: 400,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_grat_fund_rule').code: 300,
            self.env.ref('l10n_bd_hr_payroll.l10n_bd_tax_exemption_rule').code: 100,
        })
        payslip.compute_sheet()

        payslip_results = {'BASIC': 80000.0, 'EXTRA_HOURS': 500.0, 'GRAT_FUND': 300.0, 'OTHER_ALLOW': 2000.0, 'PROV_FUND': 400.0, 'SALARY_ARREARS': 3000.0, 'GROSS': 86200.0, 'TAX_CREDITS': 100.0, 'TAXABLE_AMOUNT': 57366.67, 'TAXES': -2403.33, 'NET': 83796.67}
        self._validate_payslip(payslip, payslip_results)
