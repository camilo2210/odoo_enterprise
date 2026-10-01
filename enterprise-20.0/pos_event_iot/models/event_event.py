from odoo import api, models


class EventEvent(models.Model):
    _inherit = 'event.event'

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['badge_format']
