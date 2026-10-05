# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('my')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.my'),
            structure=cls.env.ref('l10n_my_hr_payroll.hr_payroll_structure_my_employee_salary'),
            structure_type=cls.env.ref('l10n_my_hr_payroll.structure_type_employee_my'),
            version_fields={
                'wage': 7000,
            },
            resource_calendar=cls.env.ref('l10n_my_hr_payroll.resource_calendar_def_40h')
        )

    def test_01_payslip(self):
        payslip = self._generate_payslip(date(2020, 4, 1), date(2020, 4, 30))
        payslip_results = {'BASIC': 7000.0, 'GROSS': 7000.0, 'EPF_EMP': -490.0, 'EPF_EMPLR': 840.0, 'SOCSO_800_EMP': -11.9, 'SOCSO_800_EMPLR': 11.9, 'SOCSO_4_EMP': -29.75, 'SOCSO_4_EMPLR': 104.15, 'SOCSO_EMP': 41.65, 'SOCSO_EMPLR': 116.05, 'NET': 6468.35}
        self._validate_payslip(payslip, payslip_results)

    def test_02_payslip(self):
        self.employee.l10n_my_socso_exempted = True
        payslip = self._generate_payslip(date(2020, 4, 1), date(2020, 4, 30))
        payslip_results = {'BASIC': 7000.0, 'GROSS': 7000.0, 'EPF_EMP': -490.0, 'EPF_EMPLR': 840.0, 'SOCSO_800_EMP': 0.0, 'SOCSO_800_EMPLR': 0.0, 'SOCSO_4_EMP': 0.0, 'SOCSO_4_EMPLR': 74.4, 'SOCSO_EMP': 0.0, 'SOCSO_EMPLR': 74.4, 'NET': 6510.0}
        self._validate_payslip(payslip, payslip_results)

    def test_03_payslip(self):
        self.version.wage = 2000
        payslip = self._generate_payslip(date(2020, 4, 1), date(2020, 4, 30))
        payslip_results = {'BASIC': 2000.0, 'GROSS': 2000.0, 'EPF_EMP': -140.0, 'EPF_EMPLR': 260.0, 'SOCSO_800_EMP': -3.9, 'SOCSO_800_EMPLR': 3.9, 'SOCSO_4_EMP': -9.75, 'SOCSO_4_EMPLR': 34.15, 'SOCSO_EMP': 13.65, 'SOCSO_EMPLR': 38.05, 'NET': 1846.35}
        self._validate_payslip(payslip, payslip_results)

    def test_04_payslip(self):
        payslip = self._generate_payslip(date(2020, 4, 1), date(2020, 4, 30))
        payslip._set_input_values({
            'MY_GENERIC_ALW': 30,
            'MY_DA': 40,
            'MY_HRA': 50,
            'MY_CONV_ALW': 60,
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 7000.0, 'MY_GENERIC_ALW': 30.0, 'MY_CONV_ALW': 60.0, 'MY_DA': 40.0, 'MY_HRA': 50.0, 'GROSS': 7180.0, 'EPF_EMP': -503.0, 'EPF_EMPLR': 862, 'SOCSO_800_EMP': -11.9, 'SOCSO_800_EMPLR': 11.9, 'SOCSO_4_EMP': -29.75, 'SOCSO_4_EMPLR': 104.15, 'SOCSO_EMP': 41.65, 'SOCSO_EMPLR': 116.05, 'NET': 6635.35}
        self._validate_payslip(payslip, payslip_results)
