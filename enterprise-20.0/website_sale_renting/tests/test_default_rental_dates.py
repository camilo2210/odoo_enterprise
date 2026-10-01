# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

from odoo.tests import tagged

from odoo.addons.website_sale_renting.tests.common import WebsiteSaleRentingCommon


@tagged("post_install", "-at_install")
class TestDefaultRentalDates(WebsiteSaleRentingCommon):
    @freeze_time("2025-01-01")
    def test_product_page_default_rental_dates_by_nights(self):
        """Test that the default renting dates are correctly computed using the website timezone."""
        self.website.sudo().tz = "Europe/Brussels"
        hotel_room_early_check_in = self._create_product(
            name="Hotel Room Early Birds",
            rent_periodicity="nights",
            list_price=90,
            pickup_time=15,
            return_time=10,
        )

        with self.mock_request(cookies={"tz": self.website.tz}) as request:
            info = hotel_room_early_check_in.with_context(
                request.env.context
            )._get_combination_info_variant()

        # Website TZ is Europe/Brussels (pickup/return time in UTC+1)
        self.assertEqual(info["default_start_date"].hour, 14)
        self.assertEqual(info["default_end_date"].hour, 9)

    @freeze_time("2025-01-01")
    def test_add_to_cart_default_rental_dates_by_days(self):
        """Test that the default renting dates are correctly computed using the website timezone."""
        self.website.sudo().tz = "America/New_York"
        bike_for_a_day = self._create_product(name="Bike", rent_periodicity="days", list_price=20.0)

        with self.mock_request(website=self.website, cookies={"tz": self.website.tz}):
            # use partner_a from the Renting Company
            self.env.user.partner_id = self.partner
            cart = self.website._create_cart()

            # Should compute default renting dates if none are given
            cart._cart_add(product_id=bike_for_a_day.id, quantity=1)

            # Website TZ is America/New_York (pickup/return time in UTC-5)
            self.assertEqual(cart.rental_start_date.hour, 5)  # 5h (midnight in UTC-5)
            self.assertEqual(cart.rental_return_date.hour, 5)  # 5h (midnight in UTC-5)
