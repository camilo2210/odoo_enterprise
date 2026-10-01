# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestExceptionalWithholdingTaxException(TestPayrollCommon):
    """
    Test the exemption that skips the flat-rate professional withholding tax on double holiday and 13th month payslips.
    The exemption fires for any employee with zero SSCUM and a zero theoretical monthly tax, whatever the scale.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("hr_payroll.BASIC").code = "BASIC"
        cls.env.ref("hr_payroll.GROSS").code = "GROSS"
        cls.env.ref("hr_payroll.ALW").code = "ALW"

        # Structure references shared by all test methods.
        cls.monthly_structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        cls.double_holiday_structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
        cls.thirteen_month_structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')

        contract_start = date(2022, 1, 1)

        # This employee qualifies for the exemption with a moderate wage, four dependent children, and a non-working spouse.
        cls.employee_exemption = cls.create_employee({
            'name': 'Employee Exemption', 'marital': 'married', 'spouse_fiscal_status': 'without_income',
            'wage': 3500.0, 'date_version': contract_start, 'contract_date_start': contract_start,
        })
        cls.employee_exemption.children = 4

        # This employee does not qualify because the high wage produces a positive theoretical tax even after Scale II deductions.
        cls.employee_high_wage = cls.create_employee({
            'name': 'Employee High Wage', 'marital': 'married', 'spouse_fiscal_status': 'without_income',
            'wage': 7000.0, 'date_version': contract_start, 'contract_date_start': contract_start,
        })

        # This Scale I employee qualifies too, with a 5000 EUR wage, a low income spouse, and eight dependent children.
        cls.employee_low_income_spouse = cls.create_employee({
            'name': 'Employee Low Income Spouse', 'marital': 'married', 'spouse_fiscal_status': 'low_income',
            'wage': 5000.0, 'date_version': contract_start, 'contract_date_start': contract_start,
        })
        cls.employee_low_income_spouse.children = 8

        # Validating a Belgian payslip is refused when the employee language is not a Belgian one, so activate
        # one and align every employee on it.
        cls.env['res.lang']._activate_lang('fr_BE')
        all_employees = cls.employee_exemption + cls.employee_high_wage + cls.employee_low_income_spouse
        all_employees.lang = 'fr_BE'

        # Work entries are generated for the full 2022 to 2024 period so all employees can have payslips computed without gaps.
        cls.employee_exemption.generate_work_entries(contract_start, date(2024, 12, 31))
        cls.employee_high_wage.generate_work_entries(contract_start, date(2024, 12, 31))
        cls.employee_low_income_spouse.generate_work_entries(contract_start, date(2024, 12, 31))

    def _create_exceptional_payslip(self, employee, structure, date_from):
        """ Create a payslip for the given employee and structure covering the month of date_from, compute it and return it. """
        date_to = date_from + relativedelta(months=1, days=-1)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id, 'version_id': employee.version_id.id, 'struct_id': structure.id, 'date_from': date_from, 'date_to': date_to,
        })
        payslip.compute_sheet()
        return payslip

    def test_double_holiday_withholding_tax_exemption_married_four_children(self):
        """
        A married employee with a non-working spouse and four dependent children earns 3500 EUR and has no
        BEMONTHLY payslips for 2024, so SSCUM is zero. The theoretical monthly tax also works out to zero
        after Scale II and family charge deductions are applied. DH_PP must therefore be zero.
        """
        date_from = date(2024, 1, 1)
        payslip = self._create_exceptional_payslip(self.employee_exemption, self.double_holiday_structure, date_from)
        dh_pp = payslip._get_line_values(['DH_PP'])['DH_PP'][payslip.id]['total']
        self.assertEqual(dh_pp, 0.0, "No PP should apply on double holiday when both exemption conditions are met.")

    def test_thirteen_month_withholding_tax_exemption_married_four_children(self):
        """
        A married employee with a non-working spouse and four dependent children earns 3500 EUR and has no
        BEMONTHLY payslips for 2024, so SSCUM is zero. The theoretical monthly tax also works out to zero
        after Scale II and family charge deductions are applied. BONUS_PP must therefore be zero.
        """
        date_from = date(2024, 12, 1)
        payslip = self._create_exceptional_payslip(self.employee_exemption, self.thirteen_month_structure, date_from)
        bonus_pp = payslip._get_line_values(['BONUS_PP'])['BONUS_PP'][payslip.id]['total']
        self.assertEqual(bonus_pp, 0.0, "No PP should apply on the 13th month when both exemption conditions are met.")

    def test_thirteen_month_withholding_tax_exemption_low_income_spouse_eight_children(self):
        """
        A married Scale I employee with a low income spouse and eight dependent children earns 5000 EUR and
        has validated BEMONTHLY payslips whose withholding tax is zero, so SSCUM is zero despite the payslips
        existing. The theoretical monthly tax is also zero thanks to the family charge deductions, so the
        exemption must fire on the December 13th month payslip and BONUS_PP must be zero.
        """
        # Validate January and February monthly payslips to prove that zero PP payslips do not block the exemption.
        monthly_payslips = self.create_and_validate_payslips(
            self.employee_low_income_spouse, 2024, [1, 2], vals={'struct_id': self.monthly_structure.id},
        )
        monthly_pp = monthly_payslips._get_line_values(['PPTOTAL'], compute_sum=True)['PPTOTAL']['sum']['total']
        self.assertEqual(monthly_pp, 0.0, "Monthly PP must already be zero, otherwise the scenario is wrong.")

        date_from = date(2024, 12, 1)
        payslip = self._create_exceptional_payslip(
            self.employee_low_income_spouse, self.thirteen_month_structure, date_from,
        )
        bonus_pp = payslip._get_line_values(['BONUS_PP'])['BONUS_PP'][payslip.id]['total']
        self.assertEqual(bonus_pp, 0.0, "No PP on the 13th month for a Scale I employee meeting both conditions.")

    def test_no_exemption_when_theoretical_tax_is_positive(self):
        """
        A married employee with a non-working spouse, no children and a wage of 7000 EUR has no BEMONTHLY
        payslips for 2024, so SSCUM is zero. At that wage level the theoretical monthly tax is well above
        zero even after Scale II and marital deductions, so the exemption must not fire and DH_PP must be negative.
        """
        date_from = date(2024, 1, 1)
        payslip = self._create_exceptional_payslip(self.employee_high_wage, self.double_holiday_structure, date_from)
        dh_pp = payslip._get_line_values(['DH_PP'])['DH_PP'][payslip.id]['total']
        self.assertLess(dh_pp, 0.0, "PP must apply on double holiday when the theoretical monthly tax is positive.")

    def test_double_holiday_withholding_tax_exemption_no_dependents(self):
        """
        A married employee with a non-working spouse, no children and a wage of 2200 EUR has no BEMONTHLY
        payslips for 2024, so SSCUM is zero. The theoretical monthly tax reaches zero only thanks to the
        flat-rate professional fees deduction, with no family charge deduction involved. DH_PP must be zero.
        """
        contract_start = date(2022, 1, 1)
        employee = self.create_employee({
            'name': 'Employee No Dependents', 'marital': 'married', 'spouse_fiscal_status': 'without_income',
            'wage': 2200.0, 'date_version': contract_start, 'contract_date_start': contract_start,
        })
        employee.generate_work_entries(contract_start, date(2024, 12, 31))
        payslip = self._create_exceptional_payslip(employee, self.double_holiday_structure, date(2024, 1, 1))
        dh_pp = payslip._get_line_values(['DH_PP'])['DH_PP'][payslip.id]['total']
        self.assertEqual(dh_pp, 0.0, "No PP should apply once professional fees alone zero the theoretical tax.")

    def test_no_exemption_when_cumulated_professional_withholding_tax_is_positive(self):
        """
        A married employee with a non-working spouse, no children and a wage of 7000 EUR has a validated
        BEMONTHLY payslip for January 2024, making SSCUM positive. The exemption is blocked at the SSCUM
        check without reaching the theoretical tax step, so DH_PP must be negative.
        """
        # Validate a January 2024 BEMONTHLY payslip so SSCUM is positive going into the exemption check.
        self.create_and_validate_payslips(
            self.employee_high_wage, 2024, 1, vals={'struct_id': self.monthly_structure.id},
        )

        date_from = date(2024, 6, 1)
        payslip = self._create_exceptional_payslip(self.employee_high_wage, self.double_holiday_structure, date_from)
        dh_pp = payslip._get_line_values(['DH_PP'])['DH_PP'][payslip.id]['total']
        self.assertLess(dh_pp, 0.0, "PP must apply when the cumulated withholding tax (SSCUM) is positive.")
