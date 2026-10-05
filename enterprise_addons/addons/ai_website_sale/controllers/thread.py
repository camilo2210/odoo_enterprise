# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http

from odoo.addons.ai.controllers.thread import AIThreadController


class AIWebsiteSaleThreadController(AIThreadController):

    def _extend_context(self, context):
        """Override to add website context for products' preview"""
        context = super()._extend_context(context)
        # Non-website AI routes keep the host-selected website in host_id.
        website = http.request.env.website or http.request.env['website'].browse(
            http.request.env.context.get('host_id')
        )
        if website:
            # Cart is required to compute the pricelist.
            if not hasattr(http.request, 'cart'):
                http.request.cart = website._get_and_cache_current_cart()
            pricelist = website._get_and_cache_current_pricelist()
            fiscal_position = website._get_and_cache_current_fiscal_position()

            context['website_id'] = website.id
            context['pricelist_id'] = pricelist.id
            context['fiscal_position_id'] = fiscal_position.id
        return context
