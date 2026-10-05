# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart as WebsiteSaleCart


class Cart(WebsiteSaleCart):
    def _get_product_user_error(self, product):
        """Override to show a clearer error when mixing one-time and subscription products."""
        if (
            product
            and product.recurring_invoice
            and not product.allow_one_time_sale
            and request.cart._has_one_time_sale()
        ):
            return self.env._(
                "You cannot add the subscription product '%s' to a cart that already contains a one-time purchase.\n"
                "Please order them separately or empty your cart.",
                product.display_name,
            )
        return super()._get_product_user_error(product)

    @route()
    def add_to_cart(self, *args, **kwargs):
        """Override to add plan_id to request context."""
        if "plan_id" in kwargs:
            request.update_context(plan_id=kwargs["plan_id"])
        return super().add_to_cart(*args, **kwargs)
