# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _should_be_locked(self):
        self.ensure_one()
        if self.env.context.get('intervention_create_sale_order'):
            return False
        return super()._should_be_locked()

    def _get_product_catalog_product_data(self, product, **kwargs) -> dict:
        product_data = super()._get_product_catalog_product_data(product, **kwargs)
        if self.env.context.get('intervention_id'):
            product_data.update({
                'tracking': bool(product.tracking),
                'minimumQuantityOnProduct': 0,  # TODO add defaultProps/optional and remove the default here
            })
        return product_data
