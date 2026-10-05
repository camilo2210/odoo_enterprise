# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.http import request


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _resolve_product_combination_info(self):
        """Prepare website-aware combination info keyed by product ID.
        :return: {product_id: combination_info} dict, or empty dict if no website context is available.
        """
        # Outside an HTTP request we lack session-based pricing context,
        # so we fall back to the ai's pre-set context (including website pricelist and fiscal position).
        pricelist, fiscal_position = None, None
        if not request:
            pricelist, fiscal_position = self.env['product.template']._get_website_context()
        return {
            product.id: product._get_combination_info_variant(
                pricelist=pricelist,
                fiscal_position=fiscal_position,
            )
            for product in self
        }

    def _ai_get_preview_metadata(self):
        """Extend preview metadata with website combination prices."""
        metadata = super()._ai_get_preview_metadata()
        combo_info = self._resolve_product_combination_info()
        for entry in metadata:
            entry.update(combo_info.get(entry['id'], {}))
        return metadata

    def ai_set_main_image(self, attachment_id):
        self.ensure_one()
        self.image_1920 = self.env['ir.attachment'].browse(attachment_id).raw
