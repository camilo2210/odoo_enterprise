# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.tests import freeze_time
from odoo.tools import float_round

from .common import TestPlanningFieldServiceSaleTimesheetCommon


@freeze_time("2026-02-27 08:00:00")
class TestSoLineDeterminedInTimesheet(TestPlanningFieldServiceSaleTimesheetCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'project_id' in cls.intervention._fields:
            cls.intervention.project_id = cls.field_service_project
        else:
            cls.env['res.config.settings'].create({'planning_project_id': cls.field_service_project.id}).execute()
        cls.intervention.write({
            'resource_ids': cls.george_employee.resource_id.ids,
            'state': '3_in_progress',
            'partner_id': cls.partner_1.id,
        })

        cls.fsm_so = cls.env['sale.order'].create({
            'partner_id': cls.partner_1.id,
            'partner_invoice_id': cls.partner_1.id,
            'partner_shipping_id': cls.partner_1.id,
            'order_line': [
                Command.create({
                    'name': cls.product_delivery_timesheet1.name,
                    'product_id': cls.product_delivery_timesheet1.id,
                    'product_uom_qty': 10,
                    'price_unit': cls.product_delivery_timesheet1.list_price,
                }),
                Command.create({
                    'product_id': cls.product_delivery_timesheet2.id,
                    'product_uom_qty': 5,
                    'price_unit': cls.product_delivery_timesheet2.list_price,
                }),
                Command.create({
                    'product_id': cls.product_delivery_timesheet3.id,
                    'product_uom_qty': 5,
                    'price_unit': cls.product_delivery_timesheet3.list_price,
                })
            ]
        })
        cls.fsm_so.action_confirm()

    def test_fsm_sale_rounding(self):
        """
        Test rounding is correctly applied in the so line
        """
        product_uom_qty = 0.333333
        quantity_precision = self.env['decimal.precision'].precision_get('Product Unit')
        self.intervention.write({'allocated_hours': product_uom_qty, 'break_time': 0})

        with freeze_time(self.intervention.start_datetime + relativedelta(hours=product_uom_qty)):
            # validation and SO
            self.intervention.with_user(self.george_user).action_complete()
            order = self.intervention.sale_order_id
        self.assertEqual(len(self.intervention.intervention_timesheet_ids), 1)
        self.assertEqual(self.intervention.intervention_timesheet_ids.unit_amount, 0.5, "Unit amount should be rounded to 0.5")
        self.assertEqual(len(order.order_line), 1)

        expected_price_subtotal = order.order_line.price_unit * float_round(0.5, precision_digits=quantity_precision)
        self.assertAlmostEqual(
            order.order_line.price_subtotal,
            expected_price_subtotal,
            delta=quantity_precision,
            msg="Order line subtotal is not correct",
        )

    def test_sol_determined_on_timesheet_with_task_is_under_warranty(self):
        """ Test the functionality to ensure that the SOL in the timesheet is not set in the FSM project after task validation.
            - Created two tasks, one designated as "Under Warranty" and another not.
            - Validate both task.
            - Ensure that the SOL in the timesheet remains unset
                for the task marked as "Under Warranty"
        """
        self.marcel_employee.timesheet_product_id = self.product_delivery_timesheet2
        self.henri_employee.timesheet_product_id = self.product_delivery_timesheet3
        warranty_intervention, without_warranty_intervention, intervention_3, intervention_4, intervention_5 = self.env['planning.slot'].with_context({
            'mail_create_nolog': True,
            'default_resource_ids': self.george_employee.resource_id.ids,
            'default_partner_id': self.partner_1.id,
            'default_state': '3_in_progress',
        }).create([{
                'name': 'Intervention 1',
                'under_warranty': True,
                'start_datetime': datetime.now(),
                'end_datetime': datetime.now() + relativedelta(hours=2),
            }, {
                'name': 'Intervention 2',
                'start_datetime': datetime.now(),
                'end_datetime': datetime.now() + relativedelta(hours=2),
            }, {
                'name': 'Intervention 3',
                'under_warranty': True,
                'start_datetime': datetime.now(),
                'end_datetime': datetime.now() + relativedelta(hours=2),
                'sale_line_id': self.fsm_so.order_line[0].id,
            }, {
                'name': 'Intervention 4 with multiple resources',
                'under_warranty': True,
                'start_datetime': datetime.now(),
                'end_datetime': datetime.now() + relativedelta(hours=2),
                'sale_line_id': self.fsm_so.order_line[1].id,
                'resource_ids': [self.marcel_employee.resource_id.id, self.henri_employee.resource_id.id],
            }, {
                'name': 'Intervention 5 with multiple resources',
                'start_datetime': datetime.now(),
                'end_datetime': datetime.now() + relativedelta(hours=2),
                'resource_ids': [self.marcel_employee.resource_id.id, self.henri_employee.resource_id.id],
            },
        ])
        self.set_field_service_project(self.field_service_project, warranty_intervention + without_warranty_intervention + intervention_3 + intervention_4 + intervention_5)

        self.consu_product_delivered.with_context({'intervention_id': warranty_intervention.id}).set_fsm_quantity(2)
        self.consu_product_delivered.with_context({'intervention_id': without_warranty_intervention.id}).set_fsm_quantity(2)
        default_service_product = self.env.ref('sale_timesheet.time_product')

        warranty_intervention.action_complete()
        self.assertFalse(warranty_intervention.intervention_timesheet_ids.so_line, 'The timesheet should not be linked to a SOL.')
        self.assertFalse(warranty_intervention.sale_line_id, 'The intervention should not be linked to a SOL.')

        without_warranty_intervention.action_complete()
        self.assertTrue(without_warranty_intervention.intervention_timesheet_ids.so_line, 'The timesheet should be linked to a SOL.')
        self.assertTrue(without_warranty_intervention.sale_line_id, 'The intervention should be linked to a SOL.')
        self.assertEqual(without_warranty_intervention.intervention_timesheet_ids.so_line, without_warranty_intervention.sale_line_id)
        self.assertEqual(without_warranty_intervention.sale_line_id.product_id, default_service_product, 'The product used should be the default service one.')

        intervention_3.action_complete()
        self.assertTrue(intervention_3.intervention_timesheet_ids.so_line, 'The timesheet should be linked to a SOL even if the intervention is under warranty.')
        self.assertTrue(intervention_3.sale_line_id, 'The intervention shouuld be linked to the SOL set even if it is under warranty.')
        self.assertEqual(intervention_3.intervention_timesheet_ids.so_line.price_unit, 0.0, 'The price unit should be equal to 0 since the intervention is under warranty.')
        self.assertEqual(intervention_3.intervention_timesheet_ids.so_line, intervention_3.sale_line_id)

        intervention_4.action_complete()
        self.assertEqual(len(intervention_4.intervention_timesheet_ids), 2, 'One timesheet per resource assigned on the intervention should be generated.')
        self.assertEqual(self.henri_employee + self.marcel_employee, intervention_4.intervention_timesheet_ids.employee_id)
        self.assertEqual(intervention_4.sale_line_id, self.fsm_so.order_line[1], 'The SOL selected by the user should still be set on the intervention.')
        self.assertEqual(intervention_4.sale_order_id, self.fsm_so, 'The SO should still be the one selected by the user.')
        sol_per_product = intervention_4.sale_order_id.order_line.grouped('product_id')
        timesheet1, timesheet2 = intervention_4.intervention_timesheet_ids
        self.assertEqual(timesheet1.so_line, intervention_4.sale_line_id)
        self.assertEqual(timesheet2.so_line, intervention_4.sale_line_id)
        self.assertEqual(intervention_4.sale_line_id.price_unit, 0.0)

        intervention_5.action_complete()
        self.assertEqual(len(intervention_5.intervention_timesheet_ids), 2, 'One timesheet per resource assigned on the intervention should be generated.')
        self.assertEqual(self.henri_employee + self.marcel_employee, intervention_5.intervention_timesheet_ids.employee_id)
        self.assertTrue(intervention_5.sale_line_id, 'A SOL should be set on the intervention.')
        self.assertTrue(intervention_5.sale_order_id, 'A SO should be set on the intervention.')
        self.assertEqual(len(intervention_5.sale_order_id.order_line), 2, '2 SOL should be contained inside the SO linked to that intervention.')
        self.assertIn(self.henri_employee.timesheet_product_id, intervention_5.sale_order_id.order_line.product_id, 'The Service product set on Henri employee should be inside the Sales order generated.')
        self.assertIn(self.marcel_employee.timesheet_product_id, intervention_5.sale_order_id.order_line.product_id, 'The Service product set on Henri employee should be inside the Sales order generated.')
        sol_per_product = intervention_5.sale_order_id.order_line.grouped('product_id')
        for timesheet in intervention_5.intervention_timesheet_ids:
            expected_sol = sol_per_product[timesheet.employee_id.timesheet_product_id]
            self.assertEqual(timesheet.so_line, expected_sol, f'The timesheet of {timesheet.employee_id.name} should be linked to the SOL contained the product of {timesheet.employee_id.name} which is {timesheet.employee_id.timesheet_product_id.name}')
