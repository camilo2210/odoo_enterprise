# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon

from datetime import datetime, timedelta


class TestPosSalePlanningHttpCommon(TestPointOfSaleHttpCommon):

    @classmethod
    def get_default_groups(cls):
        groups = super().get_default_groups()
        return groups | cls.quick_ref('sales_team.group_sale_salesman_all_leads') | cls.quick_ref('planning.group_planning_manager')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        env = cls.env

        # Create independent (non-employee) material resources
        cls.resource1 = env["resource.resource"].sudo().create({
            "name": "Meeting Room A",
            "resource_type": "material",
        })
        cls.resource2 = env["resource.resource"].sudo().create({
            "name": "Conference Room B",
            "resource_type": "material",
        })
        cls.resource3 = env["resource.resource"].sudo().create({
            "name": "Training Room C",
            "resource_type": "material",
        })

        # Partner for the sale order (becomes the slot partner via the related field)
        cls.slot_partner = env["res.partner"].create({"name": "Slot Partner"})

        # Service product with planning enabled (needed to link sale lines to slots)
        cls.planning_product = env["product.product"].create({
            "name": "Planning Service",
            "type": "service",
            "sale_ok": True,
            "planning_enabled": True,
        })

        # Confirmed sale order — its lines will be linked to planning slots
        cls.sale_order = env["sale.order"].create({
            "partner_id": cls.slot_partner.id,
            "order_line": [
                Command.create({
                    "product_id": cls.planning_product.id,
                    "product_uom_qty": 3,
                }),
            ],
        })
        cls.sale_order.action_confirm()
        sale_line = cls.sale_order.order_line[0]

        # Product available in POS for order entry in tours
        cls.pos_product = env["product.product"].create({
            "name": "Test Product",
            "list_price": 10.0,
            "available_in_pos": True,
        })

        # Active planning slots: start 2 days ago, end 2 days from now
        now = datetime.now()
        slot_start = now - timedelta(days=2)
        slot_end = now + timedelta(days=2)

        cls.slot1 = env["planning.slot"].create({
            "resource_ids": [Command.link(cls.resource1.id)],
            "start_datetime": slot_start,
            "end_datetime": slot_end,
            "sale_line_id": sale_line.id,
        })
        cls.slot2 = env["planning.slot"].create({
            "resource_ids": [Command.link(cls.resource2.id)],
            "start_datetime": slot_start,
            "end_datetime": slot_end,
            "sale_line_id": sale_line.id,
        })
        cls.slot3 = env["planning.slot"].create({
            "resource_ids": [Command.link(cls.resource3.id)],
            "start_datetime": slot_start,
            "end_datetime": slot_end,
            "sale_line_id": sale_line.id,
        })

        # Publish the slots (state must be '2_published' for get_planning_slots)
        (cls.slot1 | cls.slot2 | cls.slot3).write({"state": "2_published"})

        # Payment method linked to resource1 and resource2 only
        cls.resource_pm_linked = env["pos.payment.method"].create({
            "name": "Resource (Linked)",
            "type": 'resource',
            "resource_ids": [Command.set([cls.resource1.id, cls.resource2.id])],
        })

        # Payment method with no linked resources — all resources are eligible
        cls.resource_pm_all = env["pos.payment.method"].create({
            "name": "Resource (All)",
            "type": 'resource',
        })

        cls.main_pos_config.write({
            "payment_method_ids": [
                Command.link(cls.resource_pm_linked.id),
                Command.link(cls.resource_pm_all.id),
            ],
        })


@tagged("post_install", "-at_install")
class TestUi(TestPosSalePlanningHttpCommon):
    def test_resource_payment_with_linked_resources(self):
        """
        Verify the flow when a resource payment method has explicitly linked
        resources: only those resources (with active slots) appear in the popup,
        search filters them by name or slot, and selecting one creates a payment
        line named "<method> (<slot display_name>)".
        """
        self.start_pos_tour("test_pos_sale_planning_with_linked_resources", login="pos_admin")

    def test_resource_payment_without_linked_resources(self):
        """
        Verify the flow when a resource payment method has no linked resources:
        all resources with active slots are shown in the popup and selecting one
        creates a correctly named payment line.
        """
        self.start_pos_tour("test_pos_sale_planning_without_linked_resources", login="pos_admin")
