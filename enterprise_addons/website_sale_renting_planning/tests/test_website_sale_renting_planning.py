import json

from datetime import date, datetime, timedelta
from freezegun import freeze_time
from zoneinfo import ZoneInfo

from odoo import Command, fields
from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools.date_utils import float_to_time


@tagged('post_install', '-at_install')
class TestWebsiteSaleRentingPlanning(PaymentHttpCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_date = datetime.today() + timedelta(days=1)
        cls.end_date = datetime.today() + timedelta(days=2)
        cls.date_format = "%Y-%m-%d %H:%M:%S"
        cls.startClassPatcher(freeze_time("2024-06-15 10:00:00"))

        cls.material_resource = cls.env["resource.resource"].create([
            {"name": "Material Resource", "resource_type": "material"}
        ])
        cls.employee = cls.env["hr.employee"].create({
            "name": "Employee",
            "contract_date_start": date.today(),
        })
        cls.planning_role = cls.env["planning.role"].create({
            'name': 'Role',
            'sync_shift_rental': True,
            'resource_ids': [cls.employee.resource_id.id],
        })
        cls.product_renting_planning = cls.env["product.product"].create({
            "name": "Product Renting Planning",
            "type": "service",
            "list_price": 100.0,
            "sale_ok": True,
            "rent_periodicity": "days",
            "website_published": True,
            "planning_enabled": True,
            "planning_role_id": cls.planning_role.id,
        })
        cls.planning_partner = cls.env["res.partner"].create({
            "name": "Customer Credee"
        })
        cls.express_checkout_billing_values = {
            "name": "Demo User",
            "email": "demo@test.com",
            "phone": "123456789",
            "street": "ooo",
            "street2": "ppp",
            "city": "ooo",
            "zip": "1200",
            "country": "US",
            "state": "CA",
        }
        cls.company.rental_resource_calendar_id = False
        cls.env.ref('base.default_website').write({
            'google_analytics_key': 'G-XXXXXXXXXXX',
        })

        def _get_sale_order(cls, confirmed=False):
            return cls.env["sale.order"].search([
                ("order_line.product_id", "=", cls.product_renting_planning.id),
                ("order_line.product_uom_qty", "=", 1),
                ("state", "=", "sale" if confirmed else "draft"),
                ("website_id", "!=", False),
            ], order="id desc", limit=1)
        cls._get_sale_order = _get_sale_order

    def _make_employee_flexible(self):
        # a flexible employee is one assigned a flexible-type calendar, so they're
        # considered available for any rental planning slot
        self.employee.resource_id.calendar_id = self.env["resource.calendar"].create({
            "name": "Flexible",
            "company_id": self.employee.company_id.id,
            "calendar_type": "undefined",
        })

    def test_renting_product_availabilities_with_off_resource(self):
        self.planning_role.resource_ids = self.employee.resource_id
        min_date_str = "2024-06-17 10:00:00"
        max_date_str = "2024-06-23 10:00:00"
        min_date = fields.Datetime.to_datetime(min_date_str)
        payload = self.build_rpc_payload({
            "product_id": self.product_renting_planning.id,
            "min_date": min_date_str,
            "max_date": max_date_str,
        })
        headers = {"Content-Type": "application/json"}
        url = "/rental/product/availabilities"
        response = self.url_open(url, data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        renting_availabilities = [
            {"start": "2024-06-17 10:00:00", "end": "2024-06-22 00:00:00", "quantity_available": 1},
            {"start": "2024-06-22 00:00:00", "end": "2024-06-22 23:59:59", "quantity_available": 0},
            {"start": "2024-06-22 23:59:59", "end": "2024-06-23 00:00:00", "quantity_available": 1},
            {"start": "2024-06-23 00:00:00", "end": "2024-06-23 10:00:00", "quantity_available": 0},
        ]
        self.assertEqual(result["renting_availabilities"], renting_availabilities)

        self.env["resource.calendar.leaves"].create([
            {
                "name": "Public Holiday (global)",
                "calendar_id": self.employee.resource_calendar_id.id,
                "date_from": min_date,
                "date_to": "2024-06-19 23:59:59",
                "resource_id": self.employee.resource_id.id,
                "count_as": "absence",
            }
        ])

        response = self.url_open(url, data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        renting_availabilities = [
            {"start": "2024-06-17 10:00:00", "end": "2024-06-19 23:59:59", "quantity_available": 0},
            {"start": "2024-06-19 23:59:59", "end": "2024-06-22 00:00:00", "quantity_available": 1},
            {"start": "2024-06-22 00:00:00", "end": "2024-06-22 23:59:59", "quantity_available": 0},
            {"start": "2024-06-22 23:59:59", "end": "2024-06-23 00:00:00", "quantity_available": 1},
            {"start": "2024-06-23 00:00:00", "end": "2024-06-23 10:00:00", "quantity_available": 0},
        ]
        self.assertEqual(result["renting_availabilities"], renting_availabilities)
        rental_order = self.env["sale.order"].create({
            "partner_id": self.planning_partner.id,
            "rental_start_date": "2024-06-20 10:00:00",
            "rental_return_date": "2024-06-22 10:00:00",
            "order_line": [
                Command.create({
                    "product_id": self.product_renting_planning.id,
                    "product_uom_qty": 1,
                })
            ],
        })
        rental_order.action_confirm()

        response = self.url_open(url, data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        renting_availabilities = [
            {"start": "2024-06-17 10:00:00", "end": "2024-06-19 23:59:59", "quantity_available": 0},
            {"start": "2024-06-19 23:59:59", "end": "2024-06-20 10:00:00", "quantity_available": 1},
            {"start": "2024-06-20 10:00:00", "end": "2024-06-22 10:00:00", "quantity_available": 0},
            {"start": "2024-06-22 10:00:00", "end": "2024-06-22 23:59:59", "quantity_available": 0},
            {"start": "2024-06-22 23:59:59", "end": "2024-06-23 00:00:00", "quantity_available": 1},
            {"start": "2024-06-23 00:00:00", "end": "2024-06-23 10:00:00", "quantity_available": 0},
        ]
        self.assertEqual(result["renting_availabilities"], renting_availabilities)

    def test_shop_page_rental_date_filter_with_planning_role(self):
        """Test shop page when rental date filters are applied and a
           planning role with a resource is configured."""
        self.planning_role.resource_ids = self.employee.resource_id
        response = self.url_open('/shop?start_date=2026-03-13+11:00:00&end_date=2026-03-16+23:00:00')

        self.assertEqual(response.status_code, 200)

    def test_payment_renting_product_available(self):
        """
        Scenario: Customer from ecommerce can book a stay offer when resources are available
        """
        self._disable_process_patcher()
        self._disable_post_process_patcher()
        payment_demo = self.env["ir.module.module"]._get("payment_demo")
        if payment_demo.state != "installed":
            self.skipTest("payment_demo module is not installed")
        provider = self._prepare_provider("demo")
        payment_method = self.env["payment.method"].search([("code", "=", "demo")], limit=1)
        self._make_employee_flexible()
        pickup_time = self.product_renting_planning.pickup_time = 18
        return_time = self.product_renting_planning.return_time = 9
        self.authenticate(None, None)
        prev_so = self._get_sale_order()
        response = self.make_jsonrpc_request("/shop/cart/add", {
            "product_template_id": self.product_renting_planning.product_tmpl_id.id,
            "product_id": self.product_renting_planning.id,
            "quantity": 1,
            "start_date": self.start_date.strftime(self.date_format),
            "end_date": self.end_date.strftime(self.date_format),
        })
        self.assertEqual(response["tracking_info"][0]["item_id"], str(self.product_renting_planning.product_tmpl_id.id), "No item found in shopping cart.")
        sale_order = self._get_sale_order()
        self.assertTrue(sale_order and (not prev_so or sale_order.id != prev_so.id), "No sale order was created from ecommerce.")
        self.assertEqual(sale_order.order_line.product_id.id, self.product_renting_planning.id, "product doesn't exist in sale order.")
        self.assertEqual(sale_order.state, "draft", "The order should be in 'draft' state.")
        self.make_jsonrpc_request("/shop/express_checkout", {
            "billing_address": self.express_checkout_billing_values,
        })
        response = self.make_jsonrpc_request(
            f"/shop/payment/transaction/{sale_order.id}",
            {
                "access_token": sale_order._portal_ensure_token(),
                "flow": "direct",
                "landing_route": "/shop/payment/validate",
                "payment_method_id": payment_method.id,
                "provider_id": provider.id,
                "token_id": None,
                "tokenization_requested": False,
            }
        )
        self.assertEqual(response["reference"], sale_order.name, "Purchase reference should be order name.")
        self.make_jsonrpc_request(
            "/payment/demo/simulate_payment",
            {
                "reference": response["reference"],
                "simulated_state": "done",
            }
        )
        self.env.ref('payment.processing_cron').method_direct_trigger()
        tx = self.env["payment.transaction"].search([("display_name", "=", sale_order.display_name)], order="id desc", limit=1)
        self.assertTrue(tx, "No transaction was created from ecommerce")
        self.assertIn(sale_order.id, tx.sale_order_ids.ids, "Sale order not in transaction.")
        self._run_post_processing()
        self.assertEqual(sale_order.state, "sale", "The order should be in 'sale' state.")
        planning_slot = sale_order.order_line.planning_slot_ids
        self.assertTrue(planning_slot, "There should be planning slots assigned for this product rental.")
        self.assertEqual(len(planning_slot), 1, "There should be exactly 1 slot allocated to the rental Period.")
        website_tz = ZoneInfo(self.company.website_id.tz)
        timezone_diff = timedelta(seconds=website_tz.utcoffset(self.start_date).total_seconds())
        picking_time = datetime.combine(self.start_date.astimezone(website_tz), float_to_time(pickup_time)) - timezone_diff
        return_time = datetime.combine(self.end_date.astimezone(website_tz), float_to_time(return_time)) - timezone_diff
        self.assertEqual(planning_slot.start_datetime, picking_time, "The planning slot should begin at the same time as the picking time.")
        self.assertEqual(planning_slot.end_datetime, return_time, "The planning slot should end at the same time as the return time.")

    @mute_logger("odoo.addons.payment.models.payment_data", "odoo.addons.payment.models.payment_transaction")
    def test_payment_renting_product_unavailable(self):
        """
        Scenario: Customer from ecommerce can't book a stay offer when resources are not available
        """
        self._make_employee_flexible()
        self.env["planning.slot"].create({
            "resource_ids": [self.employee.resource_id.id],
            "role_id": self.planning_role.id,
            "start_datetime": self.start_date,
            "end_datetime": self.end_date,
        })
        self.authenticate(None, None)
        response = self.make_jsonrpc_request("/shop/cart/add", {
            "product_template_id": self.product_renting_planning.product_tmpl_id.id,
            "product_id": self.product_renting_planning.id,
            "quantity": 1,
            "start_date": self.start_date.strftime(self.date_format),
            "end_date": self.end_date.strftime(self.date_format),
        })
        self.assertEqual(response['notifications'][0]['type'], 'warning', "A warning has been emitted.")
        self.assertFalse(self._get_sale_order(), "No sale order was created from ecommerce.")
