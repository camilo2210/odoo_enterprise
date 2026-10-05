# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_withholding_taxes_with_child_allowances')
class TestPayrollWithholdingTaxesWithChildAllowances(TestPayrollCommon):
    """
    This class includes test cases for Belgian Payroll withholding taxes computation.
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("hr_payroll.BASIC").code = "BASIC"
        cls.env.ref("hr_payroll.GROSS").code = "GROSS"
        cls.env.ref("hr_payroll.ALW").code = "ALW"

    def test_compute_13th_month_withholding_taxes_without_children(self):
        """
        Test Case:
        The calculation of Employee 13th Month Withholding taxes for an employee :
        Employee has 0 children
        Employee wage_on_payroll 2500

        Computation:
        basic = gross = monthly_revenue = wage_on_payroll
        13th_month_ONSS = gross * 13.07% = 326.75
        taxable_salary = (basic - 13th_month_ONSS) = 2500 - 326.75 = 2173.25

        monthly_ONSS = monthly_revenue * 13.07% = 326.75
        yearly_revenue = (monthly_revenue - monthly_ONSS) * 12 = 26079

        tax_rate (based on yearly_revenue) = 40.38%
        withholding_tax_amount = taxable_salary * tax_rate = 877.56
        The employee is not eligible for exoneration nor tax-rate reduction.
        """
        date_from = date(2024, 12, 1)
        date_to = date_from + relativedelta(months=+1, day=1, days=-1)
        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')
        self.employee_withholding_taxes_payslip.write({
            'struct_id': structure.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        self.employee_withholding_taxes_payslip.write({
            'date_from': date_from,
            'date_to': date_to
        })
        self.employee_withholding_taxes_payslip.compute_sheet()

        withholding_tax_amount = self.employee_withholding_taxes_payslip._get_line_values(['BONUS_PP'])['BONUS_PP'][self.employee_withholding_taxes_payslip.id]['total']
        self.assertAlmostEqual(withholding_tax_amount, -877.56)

    def test_effective_marital_status_multiple_marital_changes(self):
        """
        Scenario: Married (from last year) -> Single (Feb) -> Married (Apr)
        _get_effective_marital_at_date should return:
        - Jan/Feb: married (from previous year)
        - Mar -> Dec: single
        - Jan next year: married (next year)
        """
        employee = self.employee_withholding_taxes
        year = 2024

        # Initial version: married from last year
        employee.create_version({
            'date_version': date(year - 1, 12, 1),
            'marital': 'married',
            'spouse_fiscal_status': 'without_income',
        })

        # First change: single in March
        employee.create_version({
            'date_version': date(year, 3, 10),
            'marital': 'single',
            'spouse_fiscal_status': 'without_income',
        })

        # Second change: married again in June
        employee.create_version({
            'date_version': date(year, 6, 15),
            'marital': 'married',
            'spouse_fiscal_status': 'without_income',
        })

        test_dates = {
            "jan": date(year, 1, 15),
            "feb": date(year, 2, 20),
            "mar": date(year, 3, 15),
            "apr": date(year, 4, 20),
            "dec": date(year, 12, 10),
            "next_jan": date(year + 1, 1, 10),
        }

        # Expected effective marital statuses
        expected = {
            "jan": "married",
            "feb": "married",
            "mar": "single",
            "apr": "single",
            "dec": "single",
            "next_jan": "married",
        }

        # Check `_get_effective_marital_at_date` for each
        for label, dt in test_dates.items():
            eff_marital = employee._get_effective_marital_at_date(dt)
            self.assertEqual(
                eff_marital,
                expected[label],
                msg=f"Effective marital for {label} ({dt}) should be {expected[label]} but got {eff_marital}"
            )

    def test_withholding_taxes_single_to_married_mid_year(self):
        """
        Test that withholding taxes use the correct version based on the start of the year.

        Scenario: Single -> Married during the year:
        - Employee has two versions:
            * Previous version: single
            * Current version: married, starting mid-year
        - All payslips of that year must behave as SINGLE for withholding taxes.
        """

        employee = self.employee_withholding_taxes

        # initial version is single
        self.assertEqual(employee.version_id.marital, 'single')

        # Create a married version within same year
        married_date = date(2023, 3, 5)
        employee.create_version({
            'date_version': married_date,
            'marital': 'married',
            'spouse_fiscal_status': 'without_income',
            'eco_checks': 0,
            'l10n_be_lsa_monthly_pro_other_amount': 150,
            'wage': 2500,
        })

        structure = self.env.ref(
            'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary'
        )

        def _compute_withholding(date_from):
            date_to = date_from + relativedelta(months=+1, day=1, days=-1)
            version = employee._get_version(date_from)

            payslip = self.env['hr.payslip'].create({
                'employee_id': employee.id,
                'struct_id': structure.id,
                'date_from': date_from,
                'date_to': date_to,
                'version_id': version.id,
            })

            payslip.compute_sheet()

            return payslip._get_line_values(['P.P'])['P.P'][payslip.id]['total']

        # Payslip BEFORE marital change
        single_tax = _compute_withholding(date(2023, 2, 1))

        # Payslip AFTER marital change, still same year
        married_tax = _compute_withholding(date(2023, 4, 1))

        # Both must be computed as SINGLE
        self.assertAlmostEqual(single_tax, married_tax)

    def test_compute_13th_month_withholding_taxes_with_3_children(self):
        """
        Test Case:
        The 13th month withholding tax exemption for an employee :
        Employee has 3 children
        Employee wage_on_payroll 2500

        This employee has no monthly payslips this year, so SSCUM is zero, and the 3 children
        family deduction brings the theoretical monthly tax to zero. Both exemption conditions
        are met, so the flat-rate tax is skipped entirely and BONUS_PP must be 0.
        """
        self.employee_withholding_taxes.children = 3

        date_from = date(2024, 12, 1)
        date_to = date_from + relativedelta(months=+1, day=1, days=-1)
        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')
        self.employee_withholding_taxes_payslip.write({
            'struct_id': structure.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        self.employee_withholding_taxes_payslip.write({
            'date_from': date_from,
            'date_to': date_to
        })

        self.employee_withholding_taxes_payslip.compute_sheet()

        withholding_tax_amount = self.employee_withholding_taxes_payslip._get_line_values(['BONUS_PP'])['BONUS_PP'][self.employee_withholding_taxes_payslip.id]['total']
        self.assertAlmostEqual(withholding_tax_amount, 0.0)

    def test_compute_double_holiday_withholding_taxes_with_3_children(self):
        """
        Test Case:
        The double holiday withholding tax exemption for an employee :
        Employee has 3 children
        Employee wage_on_payroll 2500

        This employee has no monthly payslips this year, so SSCUM is zero, and the 3 children
        family deduction brings the theoretical monthly tax to zero. Both exemption conditions
        are met, so the flat-rate tax is skipped entirely and DH_PP must be 0.
        """
        self.employee_withholding_taxes.children = 3
        date_from = date(2024, 1, 1)
        date_to = date_from + relativedelta(months=+1, day=1, days=-1)
        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
        self.employee_withholding_taxes_payslip.write({
            'date_from': date_from,
            'date_to': date_to,
            'struct_id': structure.id,
        })
        self.employee_withholding_taxes_payslip.compute_sheet()

        withholding_tax_amount = self.employee_withholding_taxes_payslip._get_line_values(['DH_PP'])['DH_PP'][self.employee_withholding_taxes_payslip.id]['total']
        self.assertAlmostEqual(withholding_tax_amount, 0.0)

    def test_compute_termination_fees_withholding_taxes_with_3_children_after_2024(self):
        """
        Test Case:
        The calculation of Employee 13th Month Withholding taxes for an employee :
        Employee has 3 children
        Employee wage_on_payroll 2500
        Employee notice_duration 1 month

        Computation:
        gross_yearly_salary = wage_on_payroll * 12.92 = 32300
        annual_salary_revalued = gross_yearly_salary = 32300
        basic = (annual_salary_revalued / 12) * notice_period in months = 2691.666667
        termination_fees_ONSS = basic * 0.1307 = 351.8008338
        taxable_salary = (basic - termination_fees_ONSS) = 2691.666667 - 351.8008338 =  2339.865834

        Reference salary = 32300
        Social Contribution to Reference Salary = Reference Salary * 0.1307 = 4221.61
        Yearly Net Taxable Salary = Reference salary - Social Contribution = 32300 - 4221.61 = 28078.39
        Withholding tax rate: uses Yearly Net Taxable Salary as base -> 24.92%
        Withholding tax applies on TERM_GROSS = 2339.865834
        Children exoneration for 3 children: 27340
        Amount on which the withholding tax applies: max(0, 2339.865834 - (27340 - 2339.865834)) = 0
        -> withholding tax amount = 0
        """
        self.employee_withholding_taxes.children = 3

        date_from = date(2024, 1, 1)
        date_to = date_from + relativedelta(months=+1, day=1, days=-1)
        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        self.employee_withholding_taxes_payslip.write({
            'date_from': date_from,
            'date_to': date_to,
            'struct_id': structure.id,
        })
        self.employee_withholding_taxes_payslip._set_input_value('ND_MONTH', 1)
        self.employee_withholding_taxes_payslip.compute_sheet()

        withholding_tax_amount = self.employee_withholding_taxes_payslip._get_line_values(['TERM_PP'])['TERM_PP'][self.employee_withholding_taxes_payslip.id]['total']
        self.assertAlmostEqual(withholding_tax_amount, -587.61)

    def test_compute_termination_fees_withholding_taxes_with_3_children_before_2024(self):
        """
        Test Case:
        The calculation of Employee 13th Month Withholding taxes for an employee :
        Employee has 3 children
        Employee wage_on_payroll 2500
        Employee notice_duration 1 month

        Computation:
        gross_yearly_salary = wage_on_payroll * 12.92 = 32300
        annual_salary_revalued = gross_yearly_salary = 32300
        basic = (annual_salary_revalued / 12) * notice_period in months = 2691.666667
        termination_fees_ONSS = basic * 0.1307 = 351.8008338
        taxable_salary = (basic - termination_fees_ONSS) = 2691.666667 - 351.8008338 = 2339.865834

        yearly_revenue = 2320.13 * 12 = 27841.56
        basic_bareme = 9673.02
        marital_deduction = 2573.35
        family_charges_reduction = 4452.0
        yearly_withholding_tax_amount = 2647.67
        monthly_withholding_tax_amount = 238.86
        """
        self.employee_withholding_taxes.children = 3

        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        date_from = date(2023, 1, 1)
        date_to = date_from + relativedelta(months=+1, day=1, days=-1)
        self.employee_withholding_taxes_payslip.write({
            'date_from': date_from,
            'date_to': date_to,
            'struct_id': structure.id,
        })
        self.employee_withholding_taxes_payslip._set_input_value('ND_MONTH', 1)
        self.employee_withholding_taxes_payslip.compute_sheet()

        withholding_tax_amount = self.employee_withholding_taxes_payslip._get_line_values(['TERM_PP'])['TERM_PP'][self.employee_withholding_taxes_payslip.id]['total']
        self.assertAlmostEqual(withholding_tax_amount, -230.14)

    def test_marital_deduction_cross_border(self):
        """Cross-border → No Pr.P"""
        version = self.employee_withholding_taxes.version_id
        version.l10n_be_resident_situation = 'cross_border'
        payslip = self.employee_withholding_taxes_payslip
        payslip.date_from = date(2024, 6, 1)
        self.assertEqual(payslip._get_be_withholding_taxes_marital_deduction(), 0)

    def test_marital_deduction_non_resident_single_full_year_contract(self):
        """Non-resident, full year contract, works >= 75% in Belgium, single → BAREME I."""
        version = self.employee_withholding_taxes.version_id
        version.l10n_be_resident_situation = 'non_resident'
        payslip = self.employee_withholding_taxes_payslip
        payslip.date_from = date(2024, 6, 1)
        self.assertEqual(
            payslip._get_be_withholding_taxes_marital_deduction(),
            payslip._get_bareme_I_deduction(),
        )

    def test_marital_deduction_non_resident_married_full_year_contract(self):
        """Non-resident, full year contract, works >= 75% in Belgium, married spouse without income → BAREME II."""
        version = self.employee_withholding_taxes.version_id
        version.write({
            'l10n_be_resident_situation': 'non_resident',
            'marital': 'married',
            'spouse_fiscal_status': 'without_income',
        })
        payslip = self.employee_withholding_taxes_payslip
        payslip.date_from = date(2024, 6, 1)
        self.assertEqual(
            payslip._get_be_withholding_taxes_marital_deduction(),
            payslip._get_bareme_II_deduction(),
        )

    def test_marital_deduction_non_resident_partial_year_contract(self):
        """Non-resident, contract not covering full year → BAREME III (0) regardless of work_in_belgium_over_75."""
        version = self.employee_withholding_taxes.version_id
        version.write({
            'l10n_be_resident_situation': 'non_resident',
            'contract_date_end': date(2024, 11, 30),
        })
        payslip = self.employee_withholding_taxes_payslip
        payslip.date_from = date(2024, 8, 1)
        self.assertEqual(
            payslip._get_be_withholding_taxes_marital_deduction(),
            payslip._get_bareme_III_deduction(),
        )

    def test_marital_deduction_non_resident_works_under_75pct_in_belgium(self):
        """Non-resident, full year contract, works < 75% in Belgium → BAREME III (0)."""
        version = self.employee_withholding_taxes.version_id
        version.write({
            'l10n_be_resident_situation': 'non_resident',
            'work_in_belgium_over_75': False,
        })
        payslip = self.employee_withholding_taxes_payslip
        payslip.date_from = date(2024, 6, 1)
        self.assertEqual(
            payslip._get_be_withholding_taxes_marital_deduction(),
            payslip._get_bareme_III_deduction(),
        )

    def test_additional_child_bonus(self):
        """The child bonus is taxable remuneration, but is not subject to ONSS.

        For a monthly basic salary of 2,500 EUR and a child bonus of 100 EUR:
        - Basic salary: 2,500 EUR
        - Employee ONSS: -326.75 EUR (2,500 * 13.07%)
        - Employment bonus: 213.05 EUR (employee ONSS reduction)
        - Taxable salary: 2,486.30 EUR (2,500 - 326.75 + 213.05 + 100)
        - Accounting remuneration: 2,600 EUR (2,500 + 100)
        """
        self.employee_withholding_taxes_payslip.date_from = date(2026, 1, 1)
        self.employee_withholding_taxes.l10n_be_child_bonus = 100
        self.employee_withholding_taxes_payslip.compute_sheet()

        line_values = self.employee_withholding_taxes_payslip._get_line_values([
            'CHILD_BONUS',
            'BASIC',
            'ONSS',
            'EmpBonus.1',
            'GROSS',
            'REMUNERATION',
        ])
        payslip_id = self.employee_withholding_taxes_payslip.id
        self.assertEqual(line_values['CHILD_BONUS'][payslip_id]['total'], 100)
        self.assertEqual(line_values['BASIC'][payslip_id]['total'], 2500)
        self.assertEqual(line_values['ONSS'][payslip_id]['total'], -326.75)
        self.assertEqual(line_values['EmpBonus.1'][payslip_id]['total'], 212.96)
        self.assertEqual(line_values['GROSS'][payslip_id]['total'], 2486.21)
        self.assertEqual(line_values['REMUNERATION'][payslip_id]['total'], 2600)

    def test_disabled_spouse_tax_deduction(self):
        """
        Employee with a disabled spouse should automatically qualify for Scale 2 (Bareme II)
        and receive the corresponding family charges deduction.
        """
        employee = self.employee_withholding_taxes
        version = employee.version_id

        version.write({
            'marital': 'married',
            'disabled_spouse_bool': True,
            'spouse_fiscal_status': 'high_income',
        })

        payslip = self.employee_withholding_taxes_payslip
        payslip.date_from = date(2026, 1, 1)
        payslip.date_to = date(2026, 1, 31)

        self.assertFalse(payslip._is_eligible_for_bareme_I())
        self.assertTrue(payslip._is_eligible_for_bareme_II())

        family_deduction_with_disabled_spouse = payslip._get_be_withholding_taxes_family_charges_deduction()
        disabled_deduction_parameter = payslip._rule_parameter('disabled_dependent_deduction')
        withholding_tax_amount = self.employee_withholding_taxes_payslip._get_line_values(['P.P'])['P.P'][self.employee_withholding_taxes_payslip.id]['total']

        self.assertEqual(
            family_deduction_with_disabled_spouse,
            disabled_deduction_parameter,
            msg="Disabled spouse should add a disabled_dependent_deduction under Scale II."
        )
        self.assertEqual(withholding_tax_amount, 0, msg="Withholding tax should be 0 for an employee with a 2500 euro salary and a disabled spouse under Scale II.")
