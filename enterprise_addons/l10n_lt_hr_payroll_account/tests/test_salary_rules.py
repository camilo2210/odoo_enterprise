# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('lt')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.lt'),
            structure=cls.env.ref('l10n_lt_hr_payroll.hr_payroll_structure_lt_employee_salary'),
            structure_type=cls.env.ref('l10n_lt_hr_payroll.structure_type_employee_lt'),
            version_fields={
                'wage': 1600.0
            },
            resource_calendar=cls.env.ref('l10n_lt_hr_payroll.resource_calendar_def_40h'),
        )

    def test_payslip_1(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 1600.0, 'GROSS': 1600.0, 'TAXABLEAMOUNT': 1372.44, 'SICKAMOUNT': 0.0, 'PIT': -274.49, 'PITSICK': 0.0, 'SSC': -267.63, 'NET': 1057.89, 'SSCEMP.2': 24.29, 'SSCEMP': 24.29}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_2(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip._set_input_values({
            self.env.ref('l10n_lt_hr_payroll.l10n_lt_employees_salary_pit_last_year').code: 200.0,
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 1600.0, 'GROSS': 1600.0, 'TAXABLEAMOUNT': 1372.44, 'SICKAMOUNT': 0.0, 'PIT': -274.49, 'PITSICK': 0.0, 'PITLAST': -64.0, 'SSC': -267.63, 'NET': 993.89, 'SSCEMP.2': 24.29, 'SSCEMP': 24.29}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_3(self):
        self.employee.payroll_properties = {
            self.env.ref('l10n_lt_hr_payroll.l10n_lt_employees_salary_bik').code: 400,
        }
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip.compute_sheet()
        payslip_results = {'BASIC': 1600.0, 'BIK': 400.0, 'GROSS': 2000.0, 'TAXABLEAMOUNT': 1844.44, 'SICKAMOUNT': 0.0, 'PIT': -368.89, 'PITSICK': 0.0, 'SSC': -359.67, 'NET': 1271.45, 'SSCEMP.2': 32.65, 'SSCEMP': 32.65}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_4(self):
        self.employee.payroll_properties = {
            self.env.ref('l10n_lt_hr_payroll.l10n_lt_employees_salary_pension').code: True,
        }
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip.compute_sheet()
        payslip_results = {'BASIC': 1600.0, 'GROSS': 1600.0, 'TAXABLEAMOUNT': 1372.44, 'SICKAMOUNT': 0.0, 'PIT': -274.49, 'PITSICK': 0.0, 'SSC': -267.63, 'PENSION': -41.17, 'NET': 1016.71, 'SSCEMP.2': 24.29, 'SSCEMP': 24.29}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_5(self):
        self.employee.payroll_properties = {
            self.env.ref('l10n_lt_hr_payroll.l10n_lt_employees_salary_social_contribution_company_1').code: True,
        }
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip.compute_sheet()
        payslip_results = {'BASIC': 1600.0, 'GROSS': 1600.0, 'TAXABLEAMOUNT': 1372.44, 'SICKAMOUNT': 0.0, 'PIT': -274.49, 'PITSICK': 0.0, 'SSC': -267.63, 'NET': 1057.89, 'SSCEMP_1': 34.17, 'SSCEMP': 34.17}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_6(self):
        self.employee.version_id.l10n_lt_working_capacity = '0_25'
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip.compute_sheet()
        payslip_results = {'BASIC': 1600.0, 'GROSS': 1600.0, 'TAXABLEAMOUNTDISABLED': -645.0, 'TAXABLEAMOUNT': 2017.44, 'SICKAMOUNT': 0.0, 'PIT': -403.49, 'PITSICK': 0.0, 'SSC': -393.4, 'NET': 803.11, 'SSCEMP.2': 35.71, 'SSCEMP': 35.71}
        self._validate_payslip(payslip, payslip_results)
