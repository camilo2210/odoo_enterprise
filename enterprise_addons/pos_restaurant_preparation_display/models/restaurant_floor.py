from odoo import models, api


class RestaurantFloor(models.Model):
    _inherit = 'restaurant.floor'

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        prep_display = self.env['pos.prep.display'].browse(data['pos.prep.display'][0]['id'])
        config_ids = prep_display._get_pos_config_ids().ids
        return [('pos_config_ids', 'in', config_ids)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['name']
