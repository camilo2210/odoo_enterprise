from odoo import api, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _load_pos_data_fields(self, config):
        data_fields = super()._load_pos_data_fields(config)
        data_fields.append('resource_id')
        return data_fields
