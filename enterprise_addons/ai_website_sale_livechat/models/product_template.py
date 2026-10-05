# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models

from odoo.addons.ai_website_sale_livechat.utils import adapt_shop_design_classes_for_ai_preview


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'ai.preview.card.mixin']

    def _ai_get_preview_cards_render_context(self):
        return self._ai_build_product_preview_cards_render_context()

    def _ai_build_product_preview_cards_render_context(self, product_variants=None, combo_info_per_product=None):
        """Build QWeb render context for product preview cards.

        Operates in two ways depending on whether variant-level data is supplied:
        - **Variant** (``combo_info_per_product`` provided): prices come from
          pre-computed combination info, one entry per variant.
        - **Template** (no params): prices are resolved from template-level
          sales prices via :meth:`_resolve_product_template_pricing`.

        :param dict product_variants: optional {template: variant} mapping to pin
            which variant is previewed per template
        :param dict combo_info_per_product: optional {product_id: combination_info}
            from a cart/sale flow; when present, skips template-level price resolution
        :return: ``(template_xmlid, records_render_data, extra_classes)`` or ``False``
        :rtype: tuple | bool
        """
        website = self.env.website
        if not website:
            return False
        if combo_info_per_product is None:
            prices_by_tmpl = self._resolve_product_template_pricing()
            if not prices_by_tmpl:
                return False
        # Remap shop layout classes to card-optimized equivalents for compact AI previews.
        design_classes = adapt_shop_design_classes_for_ai_preview(
            website.shop_opt_products_design_classes
        )
        shared_context = {
            'website': website,
            'is_view_active': website.is_view_active,
            'show_variations': True,
            'show_ribbons': True,
            'design_field': design_classes,
        }
        records_render_data = []
        for template in self:
            variant = (product_variants or {}).get(template, template.product_variant_id)
            if combo_info_per_product is not None:
                info = combo_info_per_product.get(variant.id, {})
                product_prices = {'price_reduce': info.get('price')}
                if info.get('has_discounted_price'):
                    product_prices['base_price'] = info.get('list_price')
            else:
                product_prices = prices_by_tmpl.get(template.id, {})
            # Build URL params to pre-select the variant's attribute values on the product page.
            attribute_values = variant.product_template_attribute_value_ids.product_attribute_value_id
            query_params = (
                {'attribute_values': ','.join(str(attr_val.id) for attr_val in attribute_values)}
                if attribute_values else {}
            )
            records_render_data.append({
                **shared_context,
                'product': template,
                'product_variant': variant,
                'previewed_attribute_values': template._get_previewed_attribute_values(),
                'product_href': template._get_product_url(query_params=query_params),
                'ribbon': template.website_ribbon_id or self.env['product.ribbon'],
                'get_product_prices': lambda _tmpl, prices=product_prices: prices,
            })
        # Combine the scss container classes to ensure proper styling in the AI preview.
        extra_classes = ' '.join(filter(None, ['oe_website_sale', design_classes]))
        return ('website_sale.products_item', records_render_data, extra_classes)
