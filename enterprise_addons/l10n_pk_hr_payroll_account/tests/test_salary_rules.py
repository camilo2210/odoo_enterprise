# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('pk')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.pk'),
            structure=cls.env.ref('l10n_pk_hr_payroll.hr_payroll_structure_pk_employee_salary'),
            structure_type=cls.env.ref('l10n_pk_hr_payroll.structure_type_employee_pk'),
            version_fields={
                'wage': 800000,
            },
            resource_calendar=cls.env.ref('l10n_pk_hr_payroll.resource_calendar_def_40h'),
        )

    def test_tax_bracket(self):
        yearly_wages = [300000, 1000000.08, 2000000.04, 3000000, 4000000.08, 5000000.04, 6000000, 10000000.08]
        expected_taxes = [0, 4000, 94000, 276000, 516000.02, 802000.01, 1104000, 2474000.03]
        for i in range(len(yearly_wages)):
            yearly_wage = yearly_wages[i]
            tax = expected_taxes[i]
            self.employee.wage = yearly_wage / 12
            payslip = self._generate_payslip(date(2026, 7, 1), date(2026, 7, 31))
            payslip_result_2026_2nd_half = {'BASIC': self.employee.wage, 'GROSS': self.employee.wage, 'GROSSY': yearly_wage, 'TXB': tax}
            self._validate_payslip(payslip, payslip_result_2026_2nd_half, skip_lines=True)

    def test_basic_payslip(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 800000.0, 'GROSS': 800000.0, 'GROSSY': 9600000.0, 'TXB': 1920000.0, 'TXW': -160000.0, 'NET': 640000.0}
        self._validate_payslip(payslip, payslip_results)
        self.employee.wage = 833333.42
        payslip_2026 = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 31))
        payslip_results_2026 = {'BASIC': 833333.42, 'GROSS': 833333.42, 'GROSSY': 10000001.04, 'TXB': 2681000.36, 'TXW': -223416.7, 'NET': 609916.72}
        self._validate_payslip(payslip_2026, payslip_results_2026)

    def test_end_of_service_payslip(self):
        self.employee.departure_date = date(2024, 1, 31)
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 800000.0, 'GROSS': 800000.0, 'GROSSY': 9600000.0, 'TXB': 1920000.0, 'EOS': 7384616.0, 'TXW': -160000.0, 'NET': 8024616.0}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_service_payslip_2026(self):
        self.employee.departure_date = date(2026, 1, 31)
        self.employee.wage = 833333.42
        payslip_2026 = self._generate_payslip(date(2026, 1, 1), date(2026, 1, 31))
        payslip_results_2026 = {'BASIC': 833333.42, 'GROSS': 833333.42, 'GROSSY': 10000001.04, 'TXB': 2681000.36, 'EOS': 9615386.0, 'TXW': -223416.7, 'NET': 10225302.72}
        self._validate_payslip(payslip_2026, payslip_results_2026)

    def test_end_of_year_tax_adjustment(self):
        nov_payslip = self._generate_payslip(date(2024, 11, 1), date(2024, 11, 30))
        nov_payslip.action_payslip_done()
        dec_payslip = self._generate_payslip(date(2024, 12, 1), date(2024, 12, 31))
        tax_adjustment_wizard = self.env['l10n.pk.ytd.tax.adjustment.wizard'].create({
            'payslip_id': dec_payslip.id,
        })
        tax_adjustment_wizard.action_confirm_pk_adjustment()
        self._validate_payslip(dec_payslip, {'TAX_CORRECT_POS': 255000.0}, skip_lines=True)
