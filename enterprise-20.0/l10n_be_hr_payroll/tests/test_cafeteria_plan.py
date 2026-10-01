# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'cafeteria_plan')
class TestSalarySacrificeComputations(TestPayrollCommon):

    def setUp(self):
        super().setUp()

        self.employee_without_benefits = self.create_employee()

        # Benefits
        self.benefit_internet = self.env.ref("l10n_be_hr_payroll.l10n_be_internet")
        self.benefit_extra_time_off = self.env.ref("l10n_be_hr_payroll.l10n_be_extra_time_off")
        self.company_car_benefit = self.env.ref("l10n_be_hr_payroll.l10n_be_transport_company_car")

    def test_convert_gross_to_net_contribution(self):
        """
        This test checks that output values for the convert gross to net_contribution are correct.
        """
        test_version = self.employee_without_benefits.version_id
        cost_factor = test_version._get_salary_costs_factor()
        pay_frequency = 12

        amount_to_convert = 100.
        expected_converted_net = amount_to_convert * cost_factor / pay_frequency

        self.assertAlmostEqual(expected_converted_net, test_version._convert_gross_to_net_contribution(amount_to_convert), places=6)

    def test_net_contribution_is_only_applied_during_salary_config(self):
        """
        During the salary config, salary sacrifice can be converted to net contribution.
        At this point, this conversion is not to be generalised and should not be part of any systematic computation.
        So this test makes sure that, outside of the salary config flow, the HR user can manually edit values for
        salary sacrifice and this will not update the net contribution.
        """

        test_version = self.employee_without_benefits.version_id
        self.assertEqual(test_version.l10n_be_cafeteria_plan_net_contribution, 0.)
        self.assertEqual(test_version.l10n_be_cafeteria_plan_salary_sacrifice, 0.)

        test_version.internet = 1000.
        self.assertEqual(test_version.l10n_be_cafeteria_plan_net_contribution, 0.)
        self.assertEqual(test_version.l10n_be_cafeteria_plan_salary_sacrifice, 0.)

    def test_net_contribution_impacts_yearly_cost_if_cafeteria_plan_enabled(self):
        """
        Since the net contribution is a compensation for the benefits cost, that the employee contributes,
        the employer cost is therefore lowered.
        """

        self.cafeteria_plan_benefit = self.env.ref("l10n_be_hr_payroll.l10n_be_cafeteria_plan")
        self.cafeteria_plan_benefit.active = True  # enable by default

        # Add a benefit - yearly_costs increases
        test_version = self.employee_without_benefits.version_id
        initial_yearly_costs = test_version.final_yearly_costs
        test_version.internet = 1000.  # benefit cost = 12_000 €
        updated_yearly_costs = test_version.final_yearly_costs
        self.assertEqual(initial_yearly_costs, 43620.5)
        self.assertEqual(updated_yearly_costs, initial_yearly_costs + 12_000.)

        # Increase net contribution -> yearly_costs is reduced
        # Approx:
        # NET 200 -> GROSS 200 * 12 / 17 = 141,1765 €
        # Yearly => 141 * 12 = 1694.118
        test_version.l10n_be_cafeteria_plan_net_contribution = 200.
        computed_yearly_costs_after = test_version._get_yearly_cost_from_wage()

        self.assertAlmostEqual(test_version.final_yearly_costs, computed_yearly_costs_after, delta=0.001)

        self.assertTrue(test_version.final_yearly_costs < updated_yearly_costs)
        self.assertTrue(test_version.final_yearly_costs > initial_yearly_costs)

    def test_net_contribution_no_impact_on_yearly_cost_if_cafeteria_plan_disabled(self):
        """
        When the cafeteria plan benefit is disabled, setting a net contribution
        should have no impact on the employee's final yearly cost.
        """
        self.cafeteria_plan_benefit = self.env.ref("l10n_be_hr_payroll.l10n_be_cafeteria_plan")
        self.cafeteria_plan_benefit.active = False

        test_version = self.employee_without_benefits.version_id
        initial_yearly_costs = test_version.final_yearly_costs

        # At first, net contribution should be 0
        self.assertEqual(test_version.l10n_be_cafeteria_plan_net_contribution, 0.)

        # Set net contribution to something above 0
        test_version.l10n_be_cafeteria_plan_net_contribution = 200.

        # Final yearly cost should remain the same
        self.assertAlmostEqual(test_version.final_yearly_costs, initial_yearly_costs)

    def test_updating_net_contribution_doesnt_change_wage(self):
        """
        If the cafeteria plan is enabled, updating the net contribution alone should lower the yearly cost but leave the wage untouched.
        """

        self.cafeteria_plan_benefit = self.env.ref("l10n_be_hr_payroll.l10n_be_cafeteria_plan")
        self.cafeteria_plan_benefit.active = True

        test_version = self.employee_without_benefits.version_id
        initial_wage = test_version.wage
        initial_yearly_costs = test_version.final_yearly_costs

        test_version.l10n_be_cafeteria_plan_net_contribution = 200.0

        self.assertLess(test_version.final_yearly_costs, initial_yearly_costs)
        self.assertEqual(test_version.wage, initial_wage)
