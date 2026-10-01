# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

import odoo.tests
from odoo.addons.mail.tests.common import MockEmail
from . import common


@odoo.tests.tagged('-at_install', 'post_install', 'salary')
class Testl10nBeHrPayrollAccountUi(MockEmail, common.TestPayrollAccountCommon):

    @classmethod
    @freeze_time('2022-01-01 09:00:00')
    def setUpClass(cls):
        super().setUpClass()
        cls.env['fleet.vehicle'].search([('model_id', '=', cls.model_a3.id)]).driver_id = False
        cls.env.ref('base.user_admin').group_ids |= cls.env.ref('hr.group_hr_user')

    def test_ui(self):
        self._init_mail_gateway()
        with freeze_time("2022-01-01 10:00:00"):
            self.start_tour("/my", 'hr_contract_salary_tour', login='admin', timeout=350)

            new_employee_id = self.env['hr.employee'].search([('name', 'ilike', 'nathalie'), ('active', '=', False)])
            new_version = self.env['hr.version'].search([('employee_id', '=', new_employee_id.id), ('active', '=', False)])
            self.assertTrue(new_version, 'A archived contract has been created')
            self.assertTrue(new_employee_id, 'An employee has been created')
            self.assertFalse(new_employee_id.active, 'Employee is not yet active')
            self.assertEqual(new_version.bus_transport_employee_amount, 100)
            self.assertEqual(new_version._get_public_transport_reimbursed_amount('bus'), 30)
            self.assertEqual(new_version.rd_percentage, 0.75)

            # asserts that '0' values automatically filled are actually being saved
            type_children = self.env['sign.item.type'].search([('auto_field', '=', 'children')])
            children_count = self.env['sign.request.item.value'].search([
                ('sign_item_id.type_id', '=', type_children.id),
                ('sign_request_id', '=', new_version.sign_request_ids.id)
            ], limit=1)
            self.assertEqual(children_count.value, '0')

        with freeze_time("2022-01-01 10:30:00"):
            self.start_tour("/my", 'hr_contract_salary_tour_sign_again', login='admin', timeout=350)
            new_employee_id = self.env['hr.employee'].search([('name', 'ilike', 'nathalie'), ('active', '=', False)])
            vehicle = self.env['fleet.vehicle'].search([('model_id', '=', self.model_a3.id)])
            self.assertEqual(vehicle.future_driver_id, new_employee_id.work_contact_id, 'Car still has the employee as its future driver')

        with freeze_time("2022-01-01 11:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_tour_hr_sign', login='admin', timeout=350)
            # Contract is signed by new employee and HR, the new car must be created, and the allocation should be created and validated
            new_employee_id = self.env['hr.employee'].search([('name', 'ilike', 'nathalie')])
            new_version = self.env['hr.version'].search([('employee_id', '=', new_employee_id.id)])
            self.assertTrue(new_version, 'A contract has been created')
            vehicle = self.env['fleet.vehicle'].search([('company_id', '=', self.company_id.id), ('model_id', '=', self.model_a3.id)])
            self.assertTrue(vehicle, 'A vehicle Exists')
            self.assertEqual(vehicle.driver_id, new_employee_id.work_contact_id, 'Driver is set')
            self.assertEqual(vehicle.company_id, new_version.company_id, 'Vehicle is in the right company')
            self.assertEqual(vehicle, new_version.car_id, 'Car id is set properly')
            self.assertTrue(new_employee_id.active, 'Employee is now active')

            # In the new contract, we can choose to order a car in the wishlist.
            self.env['ir.config_parameter'].sudo().set_int('l10n_be_hr_payroll_fleet.l10n_max_unused_cars', 1)

        with freeze_time("2022-01-01 12:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_tour_2', login='admin', timeout=350)
            new_employee_id = self.env['hr.employee'].search([('name', 'ilike', 'Mitchell Admin 3')])
            new_version = self.env['hr.version'].search([('employee_id', '=', new_employee_id.id), ('active', '=', False)])
            vehicle = self.env['fleet.vehicle'].search([('company_id', '=', self.company_id.id), ('model_id', '=', self.model_corsa.id)])
            # The vehicle will not be created frm the choosen model until the contract is fully signed
            self.assertFalse(vehicle, 'A vehicle exits')
            self.assertTrue(new_version, 'A archived contract has been created')
            self.assertTrue(new_employee_id, 'An employee has been created')
            self.assertTrue(new_employee_id.active, 'Employee is active')

        with freeze_time("2022-01-01 13:00:00"):
            # We now fully sign the offer to see if the vehicle to order is created correctly
            self.start_tour("/odoo", 'hr_contract_salary_tour_counter_sign', login='admin', timeout=350)
            new_version = self.env['hr.version'].search([('employee_id', '=', new_employee_id.id)])
            self.assertTrue(new_version, 'A contract has been created')
            vehicle = self.env['fleet.vehicle'].search([('company_id', '=', self.company_id.id), ('model_id', '=', self.model_corsa.id)])
            self.assertTrue(vehicle, 'A vehicle has been created')
            self.assertEqual(vehicle.model_id, self.model_corsa, 'Car is right model')
            self.assertEqual(vehicle.future_driver_id, new_employee_id.work_contact_id, 'Future Driver is set correctly')
            self.assertEqual(vehicle.state_id, self.env.ref('fleet.fleet_vehicle_state_new_request'), 'Car created in right state')
            self.assertEqual(vehicle.company_id, new_version.company_id, 'Vehicle is in the right company')

    def test_ui_salary_values_with_mobility_budget(self):
        self._init_mail_gateway()
        with freeze_time("2022-01-01 10:00:00"):
            self.start_tour("/my", 'hr_contract_salary_tour_with_mobility_budget', login='admin', timeout=350)

            new_employee_id = self.env['hr.employee'].search([('name', 'ilike', 'nathalie'), ('active', '=', False)])
            new_version = self.env['hr.version'].search([('employee_id', '=', new_employee_id.id), ('active', '=', False)])
            self.assertTrue(new_version, 'A archived contract has been created')
            self.assertTrue(new_employee_id, 'An employee has been created')
            self.assertFalse(new_employee_id.active, 'Employee is not yet active')

            # Check Salary values after submit - must match the salary configurator values
            self.assertEqual(new_version.wage, 2524.11, 'Wage does not match salary configurator')
            self.assertEqual(new_version.final_yearly_costs, 56359.8, 'Employer Cost does not match salary configurator')
            self.assertEqual(new_version.l10n_be_mobility_budget_amount_monthly, 508.19, 'Monthly Mobility Budget Amount does not match salary configurator')

        with freeze_time("2022-01-01 11:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_tour_hr_sign', login='admin', timeout=350)
            # Contract is signed by new employee and HR, the new car must be created
            new_employee_id = self.env['hr.employee'].search([('name', 'ilike', 'nathalie')])
            new_version = self.env['hr.version'].search([('employee_id', '=', new_employee_id.id)])
            self.assertTrue(new_version, 'A contract has been created')
            self.assertEqual(new_employee_id.version_id, new_version, 'New contract should be the employee active contract.')

            # Check Salary values after counter sign - must match the salary configurator values
            self.assertEqual(new_employee_id.wage, 2524.11, 'Wage does not match salary configurator')
            self.assertEqual(new_employee_id.final_yearly_costs, 56359.8, 'Employer Cost does not match salary configurator')
            self.assertEqual(new_employee_id.l10n_be_mobility_budget_amount_monthly, 508.19, 'Monthly Mobility Budget Amount does not match salary configurator')
