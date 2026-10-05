# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import SA, relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.website_sale.controllers.main import WebsiteSale as CheckoutController
from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("-at_install", "post_install")
class TestRentingCheckout(WebsiteSaleRentingCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CheckoutController = CheckoutController()

    def test_checkout_impossible_if_invalid_rental_dates(self):
        now = fields.Datetime.now()
        so = self._create_so(
            order_line=[Command.create({"product_id": self.projector.id})],
            rental_start_date=now + relativedelta(weekday=SA),
            rental_return_date=now + relativedelta(weeks=1, weekday=SA),
            website_id=self.website.id,
        )
        self.company.sudo().rental_resource_calendar_id = self._create_rental_calendar({
            "monday": (9, 18),
            "tuesday": (9, 18),
            "wednesday": (9, 18),
            "thursday": (9, 18),
            "friday": (9, 18),
            "sunday": (9, 18),
        })

        with self.mock_request(path="/shop/checkout", sale_order_id=so.id):
            response = self.CheckoutController.shop_checkout()

        self.assertEqual(response.status_code, 303, "SEE OTHER")
        self.assertURLEqual(response.location, "/shop/cart")
        self.assertIn("dates are invalid", so._join_alert_messages())
