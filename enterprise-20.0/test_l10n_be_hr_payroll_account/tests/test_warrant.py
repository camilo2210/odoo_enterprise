# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'warrant')
class TestWarrant(TestPayrollBase, TestBelgiumCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.be'),
            structure=cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_warrant'),
            structure_type=cls.env.ref('hr.structure_type_employee_cp200'),
            version_fields={
                'name': 'A',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
            }
        )

    def _generate_warrant_payslip(self, **inputs):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        for code, amount in inputs.items():
            payslip._set_input_value(code, amount)
        payslip.compute_sheet()
        return payslip

    def test_warrant_without_onss(self):
        # Usual case: the benefit in kind (18%) is only subject to the withholding tax
        payslip = self._generate_warrant_payslip(WARRANT_WITHOUT_ONSS=10000.0)
        self._validate_payslip(payslip)

    def test_warrant_with_onss(self):
        # Requalified warrants: the benefit in kind is subject to ONSS like a bonus
        payslip = self._generate_warrant_payslip(WARRANT_WITH_ONSS=10000.0)
        self._validate_payslip(payslip)

    def test_warrant_custom_atn_percent(self):
        # The input overrides the 18% rule parameter
        payslip = self._generate_warrant_payslip(WARRANT_WITHOUT_ONSS=10000.0, WARRANT_ATN_PERCENT=50.0)
        self._validate_payslip(payslip)

    def test_warrant_prepaid_pp(self):
        # A withholding tax prepaid for the exact amount cancels the net out
        payslip = self._generate_warrant_payslip(WARRANT_WITHOUT_ONSS=10000.0, WARRANT_PREPAID_PP=417.96)
        self._validate_payslip(payslip)

    def test_warrant_mixed(self):
        # Both kinds on the same payslip: ONSS only on the requalified part,
        # withholding tax on the whole benefit in kind
        payslip = self._generate_warrant_payslip(WARRANT_WITHOUT_ONSS=10000.0, WARRANT_WITH_ONSS=5000.0)
        self._validate_payslip(payslip)
