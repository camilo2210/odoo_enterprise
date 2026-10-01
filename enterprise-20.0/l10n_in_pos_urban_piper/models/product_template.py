# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _prepare_urbanpiper_product_tags(self, urbanpiper_store):
        """
        Extend UrbanPiper product tags for Indian providers.

        For providers based in India, products with any tax rate other than 5%
        are considered packaged goods and must include the `packaged-good` tag.
        Doc: https://api-docs.urbanpiper.com/downstream/resources/food-aggregator-specific-constraints#zomato-zomato
        """
        tags = super()._prepare_urbanpiper_product_tags(urbanpiper_store)
        if urbanpiper_store.country_code != 'IN':
            return tags

        if any(val != 5.00 for val in self.taxes_id.mapped('amount')):
            default_tags = tags.setdefault('default', [])
            if 'packaged-good' not in tags:
                default_tags.append('packaged-good')
        return tags

    def _get_urbanpiper_unit_price(self, urbanpiper_store):
        """Return the unit price using the store's configured pricelist, if any."""
        if urbanpiper_store.country_code == 'IN' and (pricelist := urbanpiper_store.preset_id.pricelist_id):
            return pricelist.with_company(urbanpiper_store.company_id)._get_product_price(
                self, 1.0, uom=self.uom_id
            )
        return super()._get_urbanpiper_unit_price(urbanpiper_store)

    def _prepare_urbanpiper_platform_pricing(self, urbanpiper_store, company_taxes):
        """Return platform-specific pricing information for UrbanPiper.

        Indian stores don't support platform-specific pricing, so no pricing data is exported.
        Doc: https://api-docs.urbanpiper.com/downstream/api/endpoints/menu/add-update-menu#:~:text=This%20feature%20is%20available%20for%20aggregators%20outside%20India.
        """
        if urbanpiper_store.country_code == 'IN':
            return []
        return super()._prepare_urbanpiper_platform_pricing(urbanpiper_store, company_taxes)
