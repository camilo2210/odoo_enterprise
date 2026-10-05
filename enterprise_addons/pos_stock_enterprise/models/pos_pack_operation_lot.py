from odoo import api, models


class PosPackOperationLot(models.Model):
    _inherit = 'pos.pack.operation.lot'

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['lot_name']
