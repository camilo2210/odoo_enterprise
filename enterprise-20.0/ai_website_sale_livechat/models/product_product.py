# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        # Get the combination info required in the render context.
        combo_info_per_product = self._resolve_product_combination_info()
        product_variants = {
            template: products[:1]
            for template, products in self.grouped('product_tmpl_id').items()
        }
        # Use the product template's method to build the render context,
        # passing the combination info and product variants.
        return self.product_tmpl_id._ai_build_product_preview_cards_render_context(
            product_variants=product_variants,
            combo_info_per_product=combo_info_per_product,
        )
