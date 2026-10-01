# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class OboxObox(models.Model):
    _name = 'obox.obox'
    _inherit = ['pos.load.mixin', 'obox.obox']

    @api.model
    def _load_pos_self_data_fields(self, config):
        return ['id', 'serial_number', 'name', 'local_ip']
