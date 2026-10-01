# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_stock_barcode_data(self):
        data = super()._get_stock_barcode_data()
        kit_boms = self.move_ids.bom_line_id.bom_id.filtered(lambda bom: bom.type == 'phantom')
        if kit_boms:
            data_product_ids = {product['id'] for product in data['records']['product.product']}
            data_product_uom_ids = {product_uom['id'] for product_uom in data['records']['product.uom']}
            product_ids = kit_boms.product_tmpl_id.product_variant_ids.filtered(lambda prod: prod.id not in data_product_ids)
            product_uoms = product_ids.product_uom_ids.filtered(lambda prod_uom: prod_uom.id not in data_product_uom_ids)
            data['records']['product.uom'] += product_uoms.read(self.env['product.uom']._get_fields_stock_barcode(), load=False)
            data['records']['product.product'] += product_ids.read(self.env['product.product']._get_fields_stock_barcode(), load=False)

        return data
