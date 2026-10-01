# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductRibbon(models.Model):
    _inherit = "product.ribbon"

    def _is_applicable_for(self, product, price_data):
        """Override to exclude rental products from the "out of stock" ribbon.

        Rental products have availability based on a time period (temporal condition),
        which is not correctly reflected by the standard "out of stock" ribbon logic.
        """
        self.ensure_one()
        if self.assign == "out_of_stock" and product.rent_periodicity:
            return False
        return super()._is_applicable_for(product, price_data)
