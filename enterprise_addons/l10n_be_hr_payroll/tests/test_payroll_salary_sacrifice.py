# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'cafeteria_plan')
class TestSalarySacrificePayroll(TestPayrollCommon):

    def setUp(self):
        super().setUp()

        self.cafeteria_plan_benefit = self.env.ref("l10n_be_hr_payroll.l10n_be_cafeteria_plan")
        self.cafeteria_plan_benefit.active = True  # enable by default

    def test_cafeteria_plan_salary_rules(self):
        """
        The cafeteria plan comes with new salary rules. This test checks that they are applied correctly.

        1. The salary sacrifice should be included in the BASIC - which then represents the shadow salary.

        2. Employee ONSS is due on salary sacrifice.
            This test makes sure that the ONSS_BASE hold that into account.

        3. Salary sacrifice should appear on the payslip between ONSS and WITHHOlDING tax (as negative value)

        4. Net contribution is deduced from the NET basket.
        """

        # SETUP
        employee = self.employee_georges
        emp_version = employee.version_id
        payslip_without = self.create_and_validate_payslips(
            employees=[employee],
            year=2025,
            months=[1],
        )

        emp_version.write({
            'l10n_be_cafeteria_plan_salary_sacrifice': 300.,
            'l10n_be_cafeteria_plan_net_contribution': 200.,
        })

        payslip_with = self.create_and_validate_payslips(
            employees=[employee],
            year=2025,
            months=[2],
        )

        line_basic_without = payslip_without.line_ids.filtered(lambda line: line.code == 'BASIC')
        line_basic_with = payslip_with.line_ids.filtered(lambda line: line.code == 'BASIC')

        line_salary_sacrifice_onss_without = payslip_without.line_ids.filtered(lambda line: line.code == "SALARY.SACRIFICE.ONSS")
        # line_salary_sacrifice_onss_with = payslip_with.line_ids.filtered(lambda line: line.code == "SALARY.SACRIFICE.ONSS")

        line_onss_without = payslip_without.line_ids.filtered(lambda line: line.code == 'ONSS')
        line_onss_with = payslip_with.line_ids.filtered(lambda line: line.code == 'ONSS')

        line_sacrifice = payslip_with.line_ids.filtered(lambda line: line.code == 'SALARY.SACRIFICE')
        line_net_contrib = payslip_with.line_ids.filtered(lambda line: line.code == 'NET.CONTRIBUTION')

        # 1. BASIC should be equal to wage + salary sacrifice
        self.assertAlmostEqual(
            line_basic_with.total,
            line_basic_without.total + 300.0,
            places=2,
            msg="BASIC should be equal to contract wage + salary sacrifice."
        )

        # 2. Compare ONSS amount -> Should be salary_sacrifice * 13.07% higher
        expected_onss_amount = 300.0 * 0.1307
        onss_diff = abs(line_onss_with.total) - abs(line_onss_without.total)

        self.assertAlmostEqual(onss_diff, expected_onss_amount)

        self.assertAlmostEqual(
            onss_diff,
            expected_onss_amount,
            msg="ONSS amount should be higher by salary_sacrifice * 13.07%."
        )
        self.assertFalse(line_salary_sacrifice_onss_without)

        # 3. Salary sacrifice appears on payslip
        self.assertTrue(line_sacrifice, "Salary sacrifice line should exist.")
        self.assertTrue(line_sacrifice.appears_on_payslip, "Salary sacrifice should appear on the payslip.")
        self.assertAlmostEqual(line_sacrifice.total, -300.0)

        # 4. Net contribution line exists and appears on payslip
        self.assertTrue(line_net_contrib, "Net contribution line should exist.")
        self.assertTrue(line_net_contrib.appears_on_payslip, "Net contribution should appear on the payslip.")
        self.assertAlmostEqual(line_net_contrib.total, -200.0)

    def test_disabled_cafeteria_plan_salary_rules(self):
        """
        When the benefit Cafeteria Plan is disabled, the rules linked to it should be disabled as well.
        Even though net contribution and salary sacrifice values are superior to 0.
        """
        self.cafeteria_plan_benefit.active = False

        employee = self.employee_georges
        employee.version_id.write({
            'l10n_be_cafeteria_plan_salary_sacrifice': 300.0,
            'l10n_be_cafeteria_plan_net_contribution': 200.0,
        })

        payslip = self.create_and_validate_payslips(
            employees=[employee],
            year=2025,
            months=[1],
        )

        codes = payslip.line_ids.mapped('code')

        self.assertNotIn('SALARY.SACRIFICE', codes)
        self.assertNotIn('NET.CONTRIBUTION', codes)
        self.assertNotIn('SALARY.SACRIFICE.ONSS', codes)
