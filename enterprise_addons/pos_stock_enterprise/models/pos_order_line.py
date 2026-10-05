from odoo import api, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['pack_lot_ids']
