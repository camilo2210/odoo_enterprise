from odoo import models


class StockRequestCount(models.TransientModel):
    _inherit = 'stock.request.count'
    _description = 'Stock Request an Inventory Count for barcode'

    def _get_values_to_write(self):
        values = super()._get_values_to_write()
        values['has_count_requested'] = True
        return values
