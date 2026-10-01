# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart as WebsiteSaleCart


class Cart(WebsiteSaleCart):
    @route()
    def add_to_cart(self, *args, **kwargs):
        """Override to add plan_id to request context."""
        if "plan_id" in kwargs:
            request.update_context(plan_id=kwargs["plan_id"])
        return super().add_to_cart(*args, **kwargs)
