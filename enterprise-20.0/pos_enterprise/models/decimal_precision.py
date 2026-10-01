from odoo import api, models


class DecimalPrecision(models.Model):
    _inherit = 'decimal.precision'

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return []

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['name', 'digits']
