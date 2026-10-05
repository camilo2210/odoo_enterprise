# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route
from odoo.addons.website_sale.controllers.product_configurator import WebsiteSaleProductConfiguratorController


class WebsiteSaleSubscriptionProductConfiguratorController(WebsiteSaleProductConfiguratorController):
    @route()
    def website_sale_product_configurator_get_values(self, *args, **kwargs):
        """Override of `website_sale` to expose the cart's locked plan.

        If the cart already contains a subscription product with a plan, the frontend
        dialog must lock all plan selectors to that plan so all subscription products
        share the same plan.
        """
        result = super().website_sale_product_configurator_get_values(*args, **kwargs)
        result['locked_plan_id'] = request.cart.plan_id.id or False
        return result
