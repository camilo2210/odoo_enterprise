# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

import odoo.tests
from odoo.addons.hr_contract_salary.utils.hr_version import HR_VERSION_CTX_KEY
from odoo.addons.hr_contract_salary.tests.test_salary_package import TestSalaryPackageItems
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@odoo.tests.tagged('post_install_l10n', '-at_install', 'post_install')
class TestEmployeePartTimeMB(TestSalaryPackageItems, TestBelgiumCommon):

    def test_employee_part_time_with_mobility_budget(self):
        active_version = self.env['hr.version'].search([('employee_id', '=', self.employee.id), ('active', '=', True)])[0]
        active_version.wage = 5000
        active_version.resource_calendar_id.hours_per_week = 18
        self.assertEqual(active_version.final_yearly_costs, 87241.0)
        old_yearly_cost = active_version.final_yearly_costs
        active_version.holidays = 10
        active_version.work_time_rate = 0.5
        active_version.contract_date_start = date.today()
        # Activate mobility budget and check full time equivalent amounts
        active_version.l10n_be_mobility_budget = True
        active_version.l10n_be_mobility_budget_amount = 16875
        self.assertEqual(active_version.wage, 5000, "wage should not change when adding benefits")
        self.assertEqual(active_version.final_yearly_costs, 108063.56, "final_yearly_cost should change when adding benefits")
        # Reset Wage old yearly_cost before holidays to make holidays impact wage without changing yearly cost.
        active_version.with_context(salary_simulation=True).final_yearly_costs = old_yearly_cost
        self.assertEqual(active_version.final_yearly_costs, 87241.0, 'final_yearly_cost should be reset to old value')
        self.assertEqual(active_version.wage, 4223.99)
        self.assertEqual(active_version.l10n_be_mobility_budget_amount, 10205.15)
        # Make part time simulation
        active_version.with_context(
            # add the ctx key manually, as test is running in a savepoint, can't use the ctx manager
            **{
                HR_VERSION_CTX_KEY: True,
                'salary_simulation': True,
                'tracking_disable': True,
                'simulation_working_schedule': 50,
            }
        )._generate_salary_simulation_payslip()
        self.assertEqual(active_version.wage, 2112.0)
        # Should not change the mobility budget
        self.assertEqual(active_version.l10n_be_mobility_budget_amount, 10205.15)
