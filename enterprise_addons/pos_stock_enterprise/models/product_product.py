from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _load_pos_preparation_data_fields(self):
        preparation_data_fields = super()._load_pos_preparation_data_fields()
        preparation_data_fields.append('tracking')
        return preparation_data_fields
