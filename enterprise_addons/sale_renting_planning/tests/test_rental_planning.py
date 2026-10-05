# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.sale_planning.tests.test_sale_planning import TestSalePlanning


@tagged('post_install', '-at_install')
class TestRentalPlanning(TestSalePlanning):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.projector = cls.env['resource.resource'].create({
            'name': 'Projector',
            'resource_type': 'material',
        })

        cls.planning_role_projector = cls.env['planning.role'].create({
            'name': 'Projector',
            'resource_ids': [Command.link(cls.projector.id)],
        })

        cls.product_projector = cls.env['product.product'].create({
            'name': 'Projector Service',
            'type': 'service',
            'planning_enabled': True,
            'planning_role_id': cls.planning_role_projector.id,
            'sale_ok': True,
            'rent_periodicity': 'days',
        })
        cls.planning_role_junior.sync_shift_rental = True

    def test_planning_rental_sol_confirmation(self):
        plannable_employees = (
            plannable_employee1,
            plannable_employee2,
        ) = self.env['hr.employee'].create([
          {'name': 'employee 1'},
          {'name': 'employee 2'},
        ])
        self.env['resource.calendar.leaves'].create([{
            'name': 'leave',
            'date_from': datetime(2023, 10, 20, 8, 0),
            'date_to': datetime(2023, 10, 20, 17, 0),
            'resource_id': plannable_employee1.resource_id.id,
            'calendar_id': plannable_employee1.resource_calendar_id.id,
            'count_as': 'absence',
        }, {
            'name': 'Public Holiday',
            'date_from': datetime(2023, 10, 25, 0, 0, 0),
            'date_to': datetime(2023, 10, 25, 23, 59, 59),
            'calendar_id': plannable_employee1.resource_calendar_id.id,
        }])
        self.planning_role_junior.resource_ids = plannable_employees.resource_id
        self.plannable_product.write({'sale_ok': True, 'rent_periodicity': 'days'})

        basic_so, resource_time_off_so, public_holiday_so, public_holiday_so_2 = self.env['sale.order'].create([{
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2023, 9, 25, 8, 0),
            'rental_return_date': datetime(2023, 9, 28, 8, 0),
            'order_line': [
                Command.create({
                    'product_id': self.plannable_product.id,
                    'product_uom_qty': 1,
                }),
            ],
        }, {
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2023, 10, 20, 8, 0),
            'rental_return_date': datetime(2023, 10, 20, 10, 0),
            'order_line': [
                Command.create({
                    'product_id': self.plannable_product.id,
                    'product_uom_qty': 1,
                }),
            ],
        }, {
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2023, 10, 25, 8, 0),
            'rental_return_date': datetime(2023, 10, 25, 15, 0),
            'order_line': [
                Command.create({
                    'product_id': self.plannable_product.id,
                    'product_uom_qty': 1,
                }),
            ],
        }, {
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2023, 10, 25, 8, 0),
            'rental_return_date': datetime(2023, 10, 25, 15, 0),
            'order_line': [
                Command.create({
                    'product_id': self.plannable_product.id,
                    'product_uom_qty': 1,
                }),
            ],
        }])

        self.assertFalse(basic_so.order_line.planning_slot_ids, "No shift should be generated since the rental order is still in draft.")
        basic_so.order_line[0].product_uom_qty = 1
        basic_so.order_line.invalidate_recordset(['planning_slot_ids'])
        self.assertFalse(basic_so.order_line.planning_slot_ids, "No shift should be generated since the rental order is still in draft.")
        basic_so.action_confirm()
        slot = basic_so.order_line.planning_slot_ids

        self.assertTrue(slot.resource_ids, 'Slot resource_ids should not be False')
        self.assertEqual(slot.start_datetime, datetime(2023, 9, 25, 8, 0), 'Slot start datetime should be same as on SO')
        self.assertEqual(slot.end_datetime, datetime(2023, 9, 28, 8, 0), 'Slot end datetime should be same as on SO')

        self.assertEqual(basic_so.planning_hours_planned, 24.0, 'Planned hours should be set when the shift is already scheduled.')
        self.assertEqual(basic_so.planning_hours_to_plan, 0.0, 'To Plan hours should be zero when the shift is already scheduled.')

        self.assertEqual(slot.state, '2_published')

        resource_time_off_so.action_confirm()
        slot_2 = resource_time_off_so.order_line.planning_slot_ids

        self.assertEqual(slot_2.resource_ids, plannable_employee2.resource_id, 'Second resource should be assign as first resource is on Time Off')
        self.assertEqual(slot_2.state, '2_published')

        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
        })
        plannable_employee1.resource_id.calendar_id = flexible_calendar
        public_holiday_so.action_confirm()
        slot_3 = public_holiday_so.order_line.planning_slot_ids

        self.assertEqual(slot_3.resource_ids, plannable_employee1.resource_id, 'First resource should be assign on public holiday as first resource is working flexible hours')
        self.assertEqual(slot_3.state, '2_published')

        with self.assertRaises(ValidationError, msg="Error should be raised since no resource is available for the product inside Rental Order."):
            public_holiday_so_2.action_confirm()

        self.assertFalse(public_holiday_so_2.order_line.planning_slot_ids, 'No slots should be generated since the confirmation of the rental order failed due to no resource available.')

    def test_planning_rental_for_material_resource(self):
        """
        Steps:
            1) Create a rental product with the `Plan Service` enabled and the resource type set to 'Material'.
            2) Create a SO for the newly created product and confirm it.
            3) Observe the state button the shift is already planned but it incorrectly displays 'To Plan'.
        """
        so_rental = self.env['sale.order'].create([{
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2024, 12, 18, 0, 0),
            'rental_return_date': datetime(2024, 12, 19, 0, 0),
            'order_line': [
                Command.create({
                    'product_id': self.product_projector.id,
                    'product_uom_qty': 1,
                }),
            ],
        }])

        so_rental.action_confirm()
        self.assertEqual(so_rental.planning_hours_planned, 8.0, 'Planned hours should be set when the shift is already scheduled.')
        self.assertEqual(so_rental.planning_hours_to_plan, 0.0, 'To Plan hours should be zero when the shift is already scheduled.')
        self.assertEqual(len(so_rental.order_line.planning_slot_ids), 1)
        self.assertEqual(so_rental.order_line.planning_slot_ids.state, '2_published')

    def test_planning_rental_sol_slot_conflict(self):
        '''
        Steps:
        1. Create a rental service product with `Plan Services` enabled.
        2. Create a rental order with multiple lines for the same product.
        3. Confirm the rental order.
        4. Check the generated shifts - each resource should have only one shift at a time
            if no resource available generate a open shift for that.
        '''
        self.planning_role_junior.write({
            'sync_shift_rental': True,
            'resource_ids': [
                Command.set((self.employee_joseph.resource_id + self.employee_bert.resource_id).ids)
            ],
        })
        self.plannable_product.write({'sale_ok': True, 'rent_periodicity': 'days'})

        rental_order_1, rental_order_2 = self.env['sale.order'].create([
            {
                'partner_id': self.planning_partner.id,
                'rental_start_date': datetime(2024, 12, 19, 9, 0),
                'rental_return_date': datetime(2024, 12, 19, 13, 0),
                'order_line': [
                    Command.create({'product_id': self.plannable_product.id, 'product_uom_qty': 1}),
                    Command.create({'product_id': self.plannable_product.id, 'product_uom_qty': 1}),
                ],
            }, {
                'partner_id': self.planning_partner.id,
                'rental_start_date': datetime(2024, 12, 26, 14, 0),
                'rental_return_date': datetime(2024, 12, 26, 17, 0),
                'order_line': [
                    Command.create({'product_id': self.plannable_product.id, 'product_uom_qty': 1}),
                    Command.create({'product_id': self.plannable_product.id, 'product_uom_qty': 1}),
                    Command.create({'product_id': self.plannable_product.id, 'product_uom_qty': 1}),
                ],
            },
        ])

        with self.assertRaises(ValidationError, msg="No enough resource available to be able to confirm that rental order."):
            rental_order_1.action_confirm()

        resource2 = self.env['resource.resource'].create([
            {'name': 'Resource 2', 'resource_type': 'material', 'default_role_id': self.planning_role_junior.id, 'role_ids': self.planning_role_junior.ids},
        ])
        rental_order_1.action_confirm()
        ro_1_slots = rental_order_1.order_line.planning_slot_ids
        self.assertEqual(ro_1_slots.resource_ids, self.employee_joseph.resource_id + resource2, 'The shifts generated by that rental order should be assigned to 2 resources')
        self.assertEqual(len(ro_1_slots), 2, '2 shifts should be generated one per SOL inside that rental order.')

        rental_order_2.action_confirm()
        resources_already_assigned = self.env['resource.resource']
        for sol in rental_order_2.order_line:
            generated_shifts = sol.planning_slot_ids
            self.assertEqual(len(generated_shifts), 1, "One shift should be generated.")
            self.assertIn(
                generated_shifts.resource_ids,
                self.planning_role_junior.resource_ids,
                "The shift generated should be assigned to one resource linked to Junior planning role.",
            )
            if resources_already_assigned:
                self.assertNotIn(
                    generated_shifts.resource_ids,
                    resources_already_assigned,
                    "The shift generated should not be assigned to the same resource than the one generated in other SOLs.",
                )
            resources_already_assigned += generated_shifts.resource_ids
        self.assertEqual(
            len(rental_order_2.order_line.planning_slot_ids.resource_ids),
            3,
            "There should be 3 resources assigned to the shift",
        )

    def test_planning_rental_sol_confirmation_with_more_than_one_unit_ordered(self):
        projector = self.env['resource.resource'].create({
            'name': 'Projector',
            'resource_type': 'material',
        })

        planning_role_projector = self.env['planning.role'].create({
            'name': 'Projector',
            'resource_ids': [Command.link(projector.id)],
            'sync_shift_rental': True,
        })

        product_projector, service_product = self.env['product.product'].create([
            {
                'name': 'Projector Service',
                'type': 'service',
                'planning_enabled': True,
                'planning_role_id': planning_role_projector.id,
                'sale_ok': True,
                'rent_periodicity': 'days',
                'uom_id': self.env.ref('uom.product_uom_unit').id,
            },
            {
                'name': 'Service',
                'type': 'service',
                'planning_enabled': True,
                'planning_role_id': planning_role_projector.id,
                'sale_ok': True,
                'rent_periodicity': 'days',
                'uom_id': self.env.ref('uom.product_uom_hour').id,
            },
        ])

        rental_order, rental_order2 = self.env['sale.order'].create([
            {
                'partner_id': self.planning_partner.id,
                'rental_start_date': datetime(2024, 12, 18, 0, 0),
                'rental_return_date': datetime(2024, 12, 19, 0, 0),
                'order_line': [
                    Command.create({
                        'product_id': product_projector.id,
                        'product_uom_qty': 2,
                    }),
                ],
            },
            {
                'partner_id': self.planning_partner.id,
                'rental_start_date': datetime(2024, 12, 23, 0, 0),
                'rental_return_date': datetime(2024, 12, 25, 0, 0),
                'order_line': [
                    Command.create({
                        'product_id': service_product.id,
                        'product_uom_qty': 5,
                    }),
                ],
            }
        ])

        with self.assertRaises(ValidationError, msg="Error should be raised since no resource is available for the product inside Rental Order."):
            rental_order.action_confirm()

        projector2 = self.env['resource.resource'].create({
            'name': 'Projector2',
            'resource_type': 'material',
            'default_role_id': planning_role_projector.id,
            'role_ids': planning_role_projector.ids,
        })
        rental_order.action_confirm()
        self.assertEqual(len(rental_order.order_line.planning_slot_ids), 2, "2 planning slots should be generated for that rental order.")
        self.assertEqual(rental_order.order_line.planning_slot_ids.resource_ids, projector + projector2, "Both resources should be assigned to that rental order line.")

        rental_order2.action_confirm()
        self.assertEqual(len(rental_order2.order_line.planning_slot_ids), 1, "1 planning slot should be generated since the UoM of the product is Hour.")
        self.assertIn(rental_order2.order_line.planning_slot_ids.resource_ids, projector + projector2, "One of both resources created inside that test should be selected.")

    def test_action_create_order(self):
        planning_slot = self.env['planning.slot'].create({
            'resource_ids': self.projector.ids,
            'role_id': self.planning_role_projector.id,
            'start_datetime': datetime(2024, 12, 18, 0, 0),
            'end_datetime': datetime(2024, 12, 19, 0, 0),
        })
        action = planning_slot.action_create_order()
        self.assertEqual(action['res_model'], 'sale.order')
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(action['target'], 'current')
        self.assertEqual(action['res_model'], 'sale.order')
        context = action['context']
        self.assertEqual(context['default_rental_start_date'], planning_slot.start_datetime)
        self.assertEqual(context['default_rental_return_date'], planning_slot.end_datetime)
        expected_default_order_line_vals = {
            'product_id': self.product_projector.id,
            'product_uom_qty': 1,
            'planning_slot_ids': planning_slot.ids,
        }
        self.assertEqual(context['default_order_line'], [Command.create(expected_default_order_line_vals)])
        view_ids = [view_id for view_id, view_type in action['views'] if view_type == 'form']
        form_view_id = view_ids[0] if view_ids else False
        rental_order_form = Form(self.env['sale.order'].with_context(context), view=form_view_id)
        self.assertEqual(len(rental_order_form.order_line), 1)
        rental_order_form.partner_id = self.planning_partner
        rental_order_form.rental_return_date += relativedelta(days=1)
        rental_order = rental_order_form.save()
        self.assertEqual(planning_slot.end_datetime, rental_order.rental_return_date, "Make sure the dates are sync between planning slot and rental order")

        rental_order.action_confirm()
        new_slot = self.env['planning.slot'].create({
            'resource_ids': self.projector.ids,
            'role_id': self.planning_role_projector.id,
            'start_datetime': datetime(2024, 12, 20, 0, 0),
            'end_datetime': datetime(2024, 12, 21, 0, 0),
        })
        new_slot.action_add_last_order()
        self.assertEqual(rental_order.order_line.product_uom_qty, 2, "Sol should have the 2 qty after adding new shift")

    def test_confirm_rental_order_with_unavailable_resource(self):
        """
        Test rental order confirmation with unavailable resource:
        1. Confirms order and creates slot when shift sync is off.
        2. Raises ValidationError when shift sync is on.
        """
        self.env['planning.slot'].create({
            'resource_ids': self.projector.ids,
            'start_datetime': datetime(2025, 9, 18, 7, 0),
            'end_datetime': datetime(2025, 9, 19, 12, 0),
        })
        order_without_sync = self.env['sale.order'].create({
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2025, 9, 18, 8, 0),
            'rental_return_date': datetime(2025, 9, 19, 8, 0),
            'order_line': [
                Command.create({
                    'product_id': self.product_projector.id,
                    'product_uom_qty': 1,
                }),
            ],
        })
        order_without_sync.action_confirm()
        self.assertEqual(
            len(order_without_sync.order_line.planning_slot_ids),
            1,
            "Expected exactly one planning slot for the projector"
        )

        self.planning_role_projector.sync_shift_rental = True
        order_with_sync = order_without_sync.copy()
        with self.assertRaises(
            ValidationError,
            msg="Cannot confirm rental when shift sync is on and resource is unavailable"
        ):
            order_with_sync.action_confirm()

    def test_confirm_rental_order_without_sufficient_resources(self):
        """
        Test confirming a rental order when there are insufficient resources:
        1. Raises ValidationError when shift sync is enabled.
        2. Allows confirmation and creates one planning slot when shift sync is disabled.
        """
        self.planning_role_projector.sync_shift_rental = True
        order_with_sync = self.env['sale.order'].create({
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2025, 9, 18, 8, 0),
            'rental_return_date': datetime(2025, 9, 19, 8, 0),
            'order_line': [
                Command.create({
                    'product_id': self.product_projector.id,
                    'product_uom_qty': 4,
                }),
            ],
        })
        with self.assertRaises(
            ValidationError,
            msg="Cannot confirm rental when shift sync is on and resource is not enough",
        ):
            order_with_sync.action_confirm()

        self.planning_role_projector.sync_shift_rental = False
        order_without_sync = order_with_sync.copy()
        order_without_sync.action_confirm()
        self.assertEqual(
            len(order_without_sync.order_line.planning_slot_ids),
            1,
            "Expected exactly one planning slot for the projector"
        )

    def test_update_planned_dates_on_shift_to_create_a_conflict(self):
        """
        Test the user cannot update the planned dates if the shift is in conflict with another shift due to that change
        1. Create a role with `sync_shift_rental` set to True
        2. Create a resource to link it to the role created in previous step
        3. Create and confirm a SO with a rental service product using the role created in step 1
        4. Check a slot has been generated by that SO
        5. Create another SO linked to the role (created in step 1) and resource created in step 2 to another period than the one set in the SO
        6. Try to reschedule the shift created in the previous step to be in the same period than the one set in the SO. Check an error is raised due to a conflict
        """
        self.planning_role_projector.sync_shift_rental = True
        self.planning_role_projector.resource_ids = False
        resource = self.env['resource.resource'].create([
            {'name': 'Resource', 'resource_type': 'material', 'default_role_id': self.planning_role_projector.id, 'role_ids': self.planning_role_projector.ids},
        ])
        order_with_sync = self.env['sale.order'].create({
            'partner_id': self.planning_partner.id,
            'rental_start_date': datetime(2025, 9, 18, 8, 0),
            'rental_return_date': datetime(2025, 9, 19, 8, 0),
            'order_line': [
                Command.create({
                    'product_id': self.product_projector.id,
                    'product_uom_qty': 1,
                }),
            ],
        })
        order_with_sync.action_confirm()
        self.assertEqual(len(order_with_sync.order_line.planning_slot_ids), 1)
        slot = order_with_sync.order_line.planning_slot_ids
        self.assertEqual(slot.resource_ids, resource)
        self.env['planning.slot'].create({
            'start_datetime': datetime(2025, 9, 20, 8, 0),
            'end_datetime': datetime(2025, 9, 21, 8, 0),
            'resource_ids': [(6, 0, [resource.id])],
            'role_id': self.planning_role_projector.id,
        })
        with self.assertRaises(
            ValidationError,
            msg="Impossible to update the slot because it has a conflict with another slot and so it is impossible to update the rental order accordingly."
        ):
            slot.end_datetime = datetime(2025, 9, 20, 9, 0)  # create conflict with slot2

    def test_no_slots_created_for_product_without_plan_services(self):
        service_product = self.env['product.product'].create({
            'name': 'Test rental Service',
            'type': 'service',
            'sale_ok': True,
            'rent_periodicity': 'days',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })

        rental_order = self.env['sale.order'].create({
            'partner_id': self.planning_partner.id,
            'order_line': [Command.create({'product_id': service_product.id, 'product_uom_qty': 1})],
        })

        rental_order.action_confirm()
        line = rental_order.order_line

        # Ensure no slots after confirmation
        self.assertFalse(line.planning_slot_ids, "no slots should be generated since the planning_enabled is false on the product related after confirmation.")
        # Update quantity
        line.product_uom_qty = 2
        line.invalidate_recordset(['planning_slot_ids'])
        self.assertFalse(line.planning_slot_ids, "no slots should be generated since the planning_enabled is false on the product related.")

    def test_shift_publish_after_confirm_rental_order(self):
        """
        Steps:
            1) Enable sync on planning role and assign resource.
            2) Manually create a planning slot.
            3) Use "New Order" from that slot to create a rental SO.
            4) Confirm SO → slot must become published.
        """
        resource = self.employee_joseph.resource_id
        self.planning_role_junior.write({
            'sync_shift_rental': True,
            'resource_ids': [Command.set([resource.id])],
        })
        self.plannable_product.rent_periodicity = 'days'
        slot = self.env['planning.slot'].create({
            'role_id': self.planning_role_junior.id,
            'resource_ids': resource.ids,
            'start_datetime': datetime(2025, 12, 20, 9, 0),
            'end_datetime': datetime(2025, 12, 20, 17, 0),
        })

        action = slot.action_create_order()
        context = action["context"]
        view_ids = [view_id for view_id, view_type in action['views'] if view_type == 'form']
        form_view_id = view_ids[0] if view_ids else False
        rental_order_form = Form(self.env['sale.order'].with_context(context), view=form_view_id)
        rental_order_form.partner_id = self.planning_partner
        rental_order = rental_order_form.save()
        self.assertEqual(
            slot.state,
            "1_draft",
            "Slot should remain in draft after creating the order."
        )

        rental_order.action_confirm()
        self.assertEqual(
            slot.state, "2_published",
            "Slot must be published only after confirming the SO."
    )
