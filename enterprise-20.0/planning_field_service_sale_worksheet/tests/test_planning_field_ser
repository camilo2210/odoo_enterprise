# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.exceptions import UserError
from odoo.addons.planning_field_service_sale_timesheet.tests.common import TestPlanningFieldServiceSaleTimesheetCommon


class TestPlanningFieldServiceReport(TestPlanningFieldServiceSaleTimesheetCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_generate_intervention_report(self):
        self.env['res.config.settings'].create({'group_field_service_allow_customer_report': True, 'group_field_service_allow_material': True}).execute()
        self.intervention.write({'state': '3_in_progress', 'resource_ids': self.henri_employee.resource_id.ids, 'partner_id': False})
        self.assertFalse(self.intervention.material_line_product_count, "No product should be linked to a new intervention")

        with self.assertRaises(UserError, msg='Should not be able to get to material without customer set'):
            self.intervention.action_view_material()
        self.intervention.write({'partner_id': self.partner_1.id})

        expected_product_count = 1
        self.service_product_delivered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count += 1
        self.service_product_ordered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count += 1
        self.consu_product_delivered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count += 1
        self.consu_product_ordered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        product_without_list_price = self.env['product.product'].create({
            'name': 'Product 0 list price',
            'list_price': 0,
            'type': 'service',
            'invoice_policy': 'delivery',
        })
        expected_product_count += 1
        product_without_list_price.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        self.intervention.action_complete()
        html_content = self.env['ir.actions.report']._render_qweb_pdf(
            'planning_field_service.worksheet_custom', [self.intervention.id])[0].decode('utf-8').split('\n')

        product_lines_to_find_in_file = {
            '<td><span dir="auto">Acoustic Bloc Screens</span></td>',
            '<td><span dir="auto">Individual Workplace</span></td>',
            '<td><span dir="auto">Consommable product delivery</span></td>',
            '<td><span dir="auto">Consommable product ordered</span></td>',
        }

        expected_product_lines_to_find_in_file = len(product_lines_to_find_in_file)
        real_product_lines_to_find_in_file = 0

        product_should_not_find_in_file = '<td><span dir="auto">Product 0 list price</span></td>'

        for product in product_lines_to_find_in_file:
            product_found = False
            for line in html_content:
                self.assertNotIn(product_should_not_find_in_file, line, 'product_without_list_price should not be in the file because its list price is 0')

                if product in line:
                    product_found = True
                    real_product_lines_to_find_in_file += 1
                    break

            self.assertTrue(product_found, f'{product} should be in the file')

        self.assertEqual(expected_product_lines_to_find_in_file, real_product_lines_to_find_in_file)
