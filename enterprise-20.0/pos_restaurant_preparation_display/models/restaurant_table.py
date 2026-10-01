from odoo import models, api


class RestaurantTable(models.Model):
    _inherit = 'restaurant.table'

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        config_ids = [config['id'] for config in data['pos.config']]
        return [('floor_id.pos_config_ids', 'in', config_ids)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['id', 'table_number', 'floor_id']
