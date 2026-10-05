# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from dateutil.relativedelta import FR, SA, SU, relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("post_install", "-at_install")
class TestWebsiteSaleRenting(WebsiteSaleRentingCommon):
    def test_has_ecommerce_sellable_variants(self):
        product_template = self.projector.product_tmpl_id
        product_template_sudo = product_template.sudo()

        # Check that `_has_ecommerce_sellable_variants` returns True when
        # the product is active and can be rent or/and sold
        with self.mock_request():
            product_template_sudo.write({"sale_ok": False, "rent_periodicity": False})
            self.assertFalse(product_template._has_ecommerce_sellable_variants())
            product_template_sudo.write({"sale_ok": True})
            self.assertTrue(product_template._has_ecommerce_sellable_variants())
            product_template_sudo.write({"sale_ok": False, "rent_periodicity": "days"})
            self.assertFalse(product_template._has_ecommerce_sellable_variants())
            product_template_sudo.write({"sale_ok": True})
            self.assertTrue(product_template._has_ecommerce_sellable_variants())
            product_template_sudo.write({"active": False})
            self.assertFalse(product_template._has_ecommerce_sellable_variants())

    @freeze_time("2023, 1, 1")
    def test_invalid_dates(self):
        self.company.sudo().rental_resource_calendar_id = self._create_rental_calendar({
            "monday": (0, 24),
            "tuesday": (0, 24),
            "wednesday": (0, 24),
            "thursday": (0, 24),
            "friday": (0, 24),
        })
        self.website.sudo().tz = "Europe/Brussels"

        now = fields.Datetime.now()
        so = self._create_so(
            rental_start_date=now + relativedelta(weekday=SA),
            rental_return_date=now + relativedelta(weeks=1, weekday=SA),
            website_id=self.website.id,
            order_line=[Command.create({"product_id": self.computer.id})],
        )

        website_2 = (
            self.env["website"].sudo().create({"name": "Test website 2", "tz": "America/New_York"})
        )
        # Created a sale order with same dates for different website
        so_2 = so.copy({"website_id": website_2.id})
        # so_2.order_line = [Command.create({"product_id": self.computer.id})]

        self.assertTrue(
            so._get_rental_dates_error_message(),
            "Pickup and Return dates cannot be set on renting unavailabilities days",
        )
        self.assertFalse(
            so_2._get_rental_dates_error_message(),
            "Pickup and Return dates can be set on renting availabilities days",
        )

        so.write({
            "rental_start_date": now + relativedelta(weekday=FR),
            "rental_return_date": now + relativedelta(weeks=1, weekday=SA),
        })
        self.assertTrue(
            so._get_rental_dates_error_message(),
            "Return date cannot be set on a renting unavailabilities day",
        )
        so_2.write({
            "rental_start_date": now + relativedelta(weekday=FR),
            "rental_return_date": now + relativedelta(weeks=1, weekday=SA),
        })
        self.assertFalse(
            so_2._get_rental_dates_error_message(),
            "Return date can be set on a renting availabilities day",
        )

        so.write({
            "rental_start_date": now + relativedelta(weekday=SA),
            "rental_return_date": now + relativedelta(weeks=1, weekday=FR),
        })
        self.assertTrue(
            so._get_rental_dates_error_message(),
            "Start date cannot be set on a renting unavailabilities day",
        )
        so_2.write({
            "rental_start_date": now + relativedelta(weekday=SA),
            "rental_return_date": now + relativedelta(weeks=1, weekday=FR),
        })
        self.assertFalse(
            so_2._get_rental_dates_error_message(),
            "Start date can be set on a renting availabilities day",
        )

        so.write({
            "rental_start_date": now + relativedelta(weeks=1, weekday=SU),
            "rental_return_date": now,
        })
        self.assertTrue(
            so._get_rental_dates_error_message(), "Return date cannot be prior to pickup date"
        )

    def test_now_is_valid_date(self):
        with freeze_time("2023-01-02 00:00:00"):
            now = fields.Datetime.now()
            so = self.env["sale.order"].create({
                "partner_id": self.partner.id,
                "rental_start_date": now,
                "rental_return_date": now + relativedelta(weeks=1),
            })
        with freeze_time("2023-01-02 00:10:00"):  # tolerance of 15 minutes
            self.assertFalse(
                so._get_rental_dates_error_message(),
                "It should be possible to rent the product now",
            )

    def test_daylight_saving_time_change(self):
        self.website.sudo().tz = "Europe/Brussels"

        with freeze_time("2024-10-27 02:01:00 UTC"):
            self.assertFalse(self.website._is_customer_in_the_same_timezone())

        with freeze_time("2025-03-30 02:01:00 UTC"):
            self.assertFalse(self.website._is_customer_in_the_same_timezone())

    def test_cart_add_with_existing_dates(self):
        """Ensure that adding a rental product to a cart with existing rental dates
        reuses those dates and does not raise an error.
        """
        with freeze_time("2025-01-10"), self.mock_request(website=self.website) as request:
            cart = request.env.website._create_cart()
            cart._cart_add(self.projector.id)
            cart.rental_start_date = datetime(2025, 1, 15, 9, 0, 0)
            cart.rental_return_date = datetime(2025, 1, 17, 18, 0, 0)
            cart._cart_add(self.projector.id)
            self.assertEqual(cart.order_line.product_uom_qty, 2)

    def test_cart_add_day_pricing_dates(self):
        """Adding a day-priced rental product to cart with dates that include a time component
        should not raise "cannot mix different rental periods".

        When the rental date picker sends start/end dates with hours (e.g. 14:30) but the product is
        priced by Days, the time component must be normalized to the product's pickup/return time in
        the website timezone so that adding the same product from the shop card and from the product
        page always yields the same stored period.
        """
        day_product = self._create_product(is_published=True)
        self.website.sudo().tz = "Europe/Brussels"

        start_date = datetime(2025, 1, 10, 14, 30, 0)
        end_date = datetime(2025, 1, 12, 14, 30, 0)

        website = self.env.get("base.default_website")

        with freeze_time("2025-01-09 22:45:00"), self.mock_request(website=website) as request:
            cart = request.env.website._create_cart()

            cart._cart_add(day_product.id, 1, start_date=start_date, end_date=end_date)

            self.assertEqual(cart.rental_start_date, datetime(2025, 1, 9, 23, 0, 0))
            self.assertEqual(cart.rental_return_date, datetime(2025, 1, 11, 23, 0, 0))

            # Shouldn't raise on second call
            cart._cart_add(day_product.id, 1, start_date=start_date, end_date=end_date)
