from .common import TestPlanningFieldServiceSaleTimesheetCommon
from odoo.exceptions import UserError
from odoo.tools import html2plaintext
from unittest.mock import patch


class TestFsSaleWithTravelInoice(TestPlanningFieldServiceSaleTimesheetCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.field_service_travel_fees = True
        cls.travel_product = cls.env.company.travel_time_invoicing_product_id.product_variant_id
        cls.env['ir.config_parameter'].sudo().set_str('web_enterprise.token_map_box', 'test-token')

    def test_planning_with_fixed_fee(self):
        self.intervention.action_complete()
        self.assertIn(self.travel_product, self.intervention.sale_order_id.order_line.product_id)
        self.assertEqual(
            self.intervention.sale_order_id.order_line.filtered(
                lambda line: line.product_id == self.travel_product
            ).product_uom_qty,
            1,
        )

    def test_planning_without_fixed_fee(self):
        self.env.company.field_service_travel_fees = False
        self.intervention.action_complete()
        self.assertNotIn(self.travel_product, self.intervention.sale_order_id.order_line.product_id)

    def test_planning_user_without_sale_access_can_complete_with_travel_fee(self):
        """ A planning user with no access to the Sales app (i.e. not a salesman/accountant)
        must still be able to complete their own intervention when travel fees are enabled,
        as the resulting sale.order.line creation should not depend on their Sales rights. """
        self.assertFalse(self.george_user.has_group('sales_team.group_sale_salesman'))
        self.intervention.with_user(self.george_user).action_complete()
        self.assertIn(self.travel_product, self.intervention.sale_order_id.order_line.product_id)

    def test_delete_or_archive_travel_fee(self):
        with self.assertRaises(UserError):
            self.env.company.travel_time_invoicing_product_id.action_archive()
        with self.assertRaises(UserError):
            self.env.company.travel_time_invoicing_product_id.unlink()

        self.env["res.company"].get_all().field_service_travel_fees = False
        self.env.company.travel_time_invoicing_product_id.action_archive()
        self.env.company.travel_time_invoicing_product_id.unlink()
        self.assertFalse(self.env.company.travel_time_invoicing_product_id)

    def test_travel_time_quantity_with_distance(self):
        self.env.company.field_service_travel_fees_mode = 'distance'
        self.george_employee.address_id = self.env['res.partner'].create({
            'name': 'A Test Partner',
            'partner_latitude': 50.3,
            'partner_longitude': 10.1,
        })
        self.intervention.partner_id.write({
            'partner_latitude': 50.5,
            'partner_longitude': 4.3,
        })

        with patch.object(
            self.env['planning.slot'].__class__,
            '_fetch_mapbox_driving_route',
            return_value=({'distance': 12600}, None),
        ):
            self.assertEqual(self.intervention._get_travel_fee_quantity(), 13)
            self.intervention.action_complete()

        self.assertIn(self.travel_product, self.intervention.sale_order_id.order_line.product_id)
        self.assertEqual(
            self.intervention.sale_order_id.order_line.filtered(
                lambda line: line.product_id == self.travel_product
            ).product_uom_qty,
            13,
        )

    def test_travel_time_quantity_missing_technician_location(self):
        self.env.company.field_service_travel_fees_mode = 'distance'
        self.george_employee.address_id = self.env['res.partner'].create({'name': 'A Test Partner 2'})
        self.intervention.partner_id.write({
            'partner_latitude': 50.5,
            'partner_longitude': 4.3,
        })

        self.assertFalse(self.intervention._get_travel_fee_quantity())
        self.assertEqual(
            html2plaintext(self.intervention.message_ids[0].body),
            "Travel time couldn't be invoiced because the customer's or technician's work address couldn't be located.",
        )
        self.intervention.action_complete()
        self.assertNotIn(self.travel_product, self.intervention.sale_order_id.order_line.product_id)

    def test_travel_time_quantity_missing_customer_location(self):
        self.env.company.field_service_travel_fees_mode = 'distance'
        self.george_employee.address_id = self.env['res.partner'].create({
            'name': 'A Test Partner',
            'partner_latitude': 50.3,
            'partner_longitude': 10.1,
        })

        self.assertFalse(self.intervention._get_travel_fee_quantity())
        self.assertEqual(
            html2plaintext(self.intervention.message_ids[0].body),
            "Travel time couldn't be invoiced because the customer's or technician's work address couldn't be located.",
        )
        self.intervention.action_complete()
        self.assertNotIn(self.travel_product, self.intervention.sale_order_id.order_line.product_id)

    def test_travel_time_quantity_round_up_distance(self):
        self.env.company.field_service_travel_fees_mode = 'distance'
        self.george_employee.address_id = self.env['res.partner'].create({
            'name': 'A Test Partner',
            'partner_latitude': 50.3,
            'partner_longitude': 10.1,
        })
        self.intervention.partner_id.write({
            'partner_latitude': 50.5,
            'partner_longitude': 4.3,
        })
        with patch.object(
            self.env['planning.slot'].__class__,
            '_fetch_mapbox_driving_route',
            return_value=({'distance': 500}, None),
        ):
            self.intervention.action_complete()

        self.assertEqual(
            self.intervention.sale_order_id.order_line.filtered(
                lambda line: line.product_id == self.travel_product
            ).product_uom_qty,
            1,
        )

    def test_travel_time_quantity_mapbox_failure(self):
        self.env.company.field_service_travel_fees_mode = 'distance'
        self.george_employee.address_id = self.env['res.partner'].create({
            'name': 'A Test Partner',
            'partner_latitude': 50.3,
            'partner_longitude': 10.1,
        })
        self.intervention.partner_id.write({
            'partner_latitude': 50.5,
            'partner_longitude': 4.3,
        })
        with patch.object(
            self.env['planning.slot'].__class__,
            '_fetch_mapbox_driving_route',
            return_value=(None, None),
        ):
            self.intervention.action_complete()

        self.assertEqual(
            html2plaintext(self.intervention.message_ids[0].body),
            "Travel time couldn't be invoiced because Mapbox could not be reached.",
        )
        self.assertNotIn(self.travel_product, self.intervention.sale_order_id.order_line.product_id)
