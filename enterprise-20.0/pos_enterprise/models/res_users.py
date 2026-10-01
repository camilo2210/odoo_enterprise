# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [('id', '=', self.env.uid)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['name']
