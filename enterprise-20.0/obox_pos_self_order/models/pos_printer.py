# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    @api.model
    def _load_pos_self_data_fields(self, config):
        fields = super()._load_pos_self_data_fields(config)
        return fields + ['proxy_obox_id']
