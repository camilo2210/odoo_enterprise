# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('ma')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.ma'),
            structure=cls.env.ref('l10n_ma_hr_payroll.hr_payroll_salary_ma_structure_base'),
            structure_type=cls.env.ref('l10n_ma_hr_payroll.structure_type_employee_mar'),
            version_fields={
                'wage': 5000,
                'contract_date_start': date(2021, 1, 1),
            },
            resource_calendar=cls.env.ref('l10n_ma_hr_payroll.resource_calendar_def_40h')
        )

    def test_cnss_rule(self):
        payslip = self._generate_payslip(date(2021, 1, 1), date(2021, 1, 31))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, 'E_CNSS': 224.0, 'JOB_LOSS_ALW': 9.5, 'E_AMO': 9.5, 'MEDICAL_ALW': 113.0, 'CIMR': 150.0, 'PRO_CONTRIBUTION': 150.0, 'TOTAL_UT_DED': 656.0, 'GROSS_TAXABLE': 4344.0, 'GROSS_INCOME_TAX': 202.13, 'FAMILY_CHARGE': 0.0, 'NET_INCOME_TAX': 202.13, 'SOCIAL_CONTRIBUTION': 0.0, 'NET': 3939.74}
        self._validate_payslip(payslip, payslip_results)

        self.version.wage = 5600
        payslip = self._generate_payslip(date(2022, 5, 1), date(2022, 5, 31))
        payslip_results = {'BASIC': 5600.0, 'GROSS': 5600.0, 'E_CNSS': 250.88, 'JOB_LOSS_ALW': 10.64, 'E_AMO': 10.64, 'MEDICAL_ALW': 126.56, 'CIMR': 168.0, 'PRO_CONTRIBUTION': 168.0, 'TOTAL_UT_DED': 734.72, 'GROSS_TAXABLE': 4865.28, 'GROSS_INCOME_TAX': 306.39, 'FAMILY_CHARGE': 0.0, 'NET_INCOME_TAX': 306.39, 'SOCIAL_CONTRIBUTION': 0.0, 'NET': 4252.51}
        self._validate_payslip(payslip, payslip_results)

        self.version.wage = 6000
        payslip = self._generate_payslip(date(2022, 6, 1), date(2022, 6, 30))
        payslip_results = {'BASIC': 6000.0, 'GROSS': 6000.0, 'E_CNSS': 268.8, 'JOB_LOSS_ALW': 11.4, 'E_AMO': 11.4, 'MEDICAL_ALW': 135.6, 'CIMR': 180.0, 'PRO_CONTRIBUTION': 180.0, 'TOTAL_UT_DED': 787.2, 'GROSS_TAXABLE': 5212.8, 'GROSS_INCOME_TAX': 397.17, 'FAMILY_CHARGE': 0.0, 'NET_INCOME_TAX': 397.17, 'SOCIAL_CONTRIBUTION': 0.0, 'NET': 4418.46}
        self._validate_payslip(payslip, payslip_results)

        self.version.wage = 7500
        payslip = self._generate_payslip(date(2023, 1, 1), date(2023, 1, 31))
        payslip_results = {'BASIC': 7500.0, 'SENIORITY': 0.0, 'GROSS': 7500.0, 'E_CNSS': 268.8, 'JOB_LOSS_ALW': 14.25, 'E_AMO': 14.25, 'MEDICAL_ALW': 169.5, 'CIMR': 225.0, 'PRO_CONTRIBUTION': 225.0, 'TOTAL_UT_DED': 916.8, 'GROSS_TAXABLE': 6583.2, 'GROSS_INCOME_TAX': 808.29, 'FAMILY_CHARGE': 0.0, 'NET_INCOME_TAX': 808.29, 'SOCIAL_CONTRIBUTION': 0.0, 'NET': 4966.62}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_property_inputs(self):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip._set_input_values({
            self.env.ref('l10n_ma_hr_payroll.l10n_ma_hr_rule_extra_hours_25').code: 1.0,
            self.env.ref('l10n_ma_hr_payroll.l10n_ma_hr_rule_extra_hours_50').code: 1.0,
            self.env.ref('l10n_ma_hr_payroll.l10n_ma_hr_rule_extra_hours_100').code: 1.0,
            self.env.ref('l10n_ma_hr_payroll.l10n_ma_hr_salary_rule_av_sal').code: 1000.0,
            self.env.ref('l10n_ma_hr_payroll.l10n_ma_hr_rule_misc_taxable_indemnity').code: 400.0,
            self.env.ref('l10n_ma_hr_payroll.l10n_ma_hr_rule_misc_non_taxable_indemnity').code: 250.0,
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 5000.0, 'EXTRA_HOURS_25': 35.51, 'EXTRA_HOURS_50': 42.61, 'EXTRA_HOURS_100': 56.82, 'SENIORITY': 250.0, 'INDMTD': 400.0, 'INDMNTD': 250.0, 'GROSS': 6034.94, 'E_CNSS': 268.8, 'JOB_LOSS_ALW': 11.47, 'E_AMO': 11.47, 'MEDICAL_ALW': 136.39, 'CIMR': 181.05, 'PRO_CONTRIBUTION': 181.05, 'TOTAL_UT_DED': 790.22, 'GROSS_TAXABLE': 5244.72, 'GROSS_INCOME_TAX': 406.75, 'FAMILY_CHARGE': 0.0, 'NET_INCOME_TAX': 406.75, 'SOCIAL_CONTRIBUTION': 0.0, 'AVS': -1000.0, 'NET': 5431.23}
        self._validate_payslip(payslip, payslip_results)
