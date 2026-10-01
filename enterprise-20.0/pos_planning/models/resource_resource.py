# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResourceResource(models.Model):
    _name = 'resource.resource'
    _inherit = ['resource.resource', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('active', '=', True), ('resource_type', '=', 'user')]
