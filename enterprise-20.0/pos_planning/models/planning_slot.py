# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PlanningSlot(models.Model):
    _name = 'planning.slot'
    _inherit = ['planning.slot', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        return [
            ('role_id.pos_config_ids', 'in', data['pos.config'].id),
            ('state', '=', '2_published'),
        ]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['start_datetime', 'end_datetime', 'state', 'resource_ids', 'role_id']
