# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PlanningSlot(models.Model):
    _name = 'planning.slot'
    _inherit = 'planning.slot'

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ['display_name', 'partner_id']
