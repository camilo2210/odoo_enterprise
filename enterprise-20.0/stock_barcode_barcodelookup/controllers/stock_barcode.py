from odoo.http import request
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController


class StockBarcodeBarcodeLookup(StockBarcodeController):

    def _get_groups_data(self):
        group_data = super()._get_groups_data()
        group_data.update({
            'group_product_manager': request.env.user.has_group(
                'product.group_product_manager'
            )
        })
        return group_data
