from odoo import fields
from .common import TestProjectTimesheetForecastFieldServiceSaleCommon


class TestPlanningSlot(TestProjectTimesheetForecastFieldServiceSaleCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_partner_id_defaults_to_delivery_address(self):
        """ Ensure that when a project or task is selected on a shift,
            the partner_id defaults to the delivery address of the customer.
        """
        delivery_address = self.env['res.partner'].create({
            'name': 'Partner 1 Warehouse',
            'parent_id': self.partner_1.id,
            'type': 'delivery',
        })

        self.task.partner_id = self.partner_1.id

        slot_task = self.env['planning.slot'].create({
            'name': 'Shift for Task',
            'task_id': self.task.id,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
        })

        self.assertEqual(
            slot_task.partner_id,
            delivery_address,
            "The shift's partner_id should default to the task customer's delivery address."
        )

        self.field_service_project.partner_id = self.partner_1.id

        slot_project = self.env['planning.slot'].create({
            'name': 'Shift for Project',
            'project_id': self.field_service_project.id,
            'start_datetime': fields.Datetime.now().replace(hour=13, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=17, minute=0, second=0),
        })

        self.assertEqual(
            slot_project.partner_id,
            delivery_address,
            "The shift's partner_id should default to the project customer's delivery address."
        )
