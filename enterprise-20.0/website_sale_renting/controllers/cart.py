# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart as WebsiteSaleCart


class Cart(WebsiteSaleCart):
    @route(
        "/shop/cart/update_renting", type="jsonrpc", auth="public", methods=["POST"], website=True
    )
    def update_cart_renting(self, start_date=None, end_date=None):
        """Route to check the cart availability when changing the dates on the cart."""
        try:
            start_date = fields.Datetime.to_datetime(start_date)
            end_date = fields.Datetime.to_datetime(end_date)
        except ValueError:
            start_date = end_date = None
        if not (start_date and end_date and (order_sudo := request.cart)):
            return {}

        order_sudo._check_not_partially_paid()  # Prevent modifying the cart if it's partially paid
        warning = order_sudo._cart_update_renting_period(start_date, end_date)

        return {
            "start_date": order_sudo.rental_start_date,
            "end_date": order_sudo.rental_return_date,
            "warning": warning,
            "values": self._get_updated_cart_page_values(order_sudo),
        }

    @route()
    def add_to_cart(self, *args, start_date=None, end_date=None, **kwargs):
        """Override to parse to datetime optional pickup and return dates."""
        start_date = fields.Datetime.to_datetime(start_date)
        end_date = fields.Datetime.to_datetime(end_date)
        return super().add_to_cart(*args, start_date=start_date, end_date=end_date, **kwargs)
