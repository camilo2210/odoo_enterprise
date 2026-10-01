# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PlanningRole(models.Model):
    _name = 'planning.role'
    _inherit = ['planning.role', 'pos.load.mixin']

    pos_config_ids = fields.Many2many('pos.config', string='Point of Sales')

    @api.model
    def _load_pos_data_domain(self, data):
        return [('pos_config_ids', 'in', data['pos.config'].id)]
