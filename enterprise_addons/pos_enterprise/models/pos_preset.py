from odoo import models, api


class PosPreset(models.Model):
    _inherit = "pos.preset"

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        available_preset_ids = data['pos.prep.display']._get_pos_config_ids().available_preset_ids
        return [('id', 'in', available_preset_ids.ids)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['name', 'use_timing', 'identification', 'slots_per_interval', 'interval_time', 'attendance_ids', 'color']
