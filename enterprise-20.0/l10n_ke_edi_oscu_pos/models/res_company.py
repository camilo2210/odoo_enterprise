# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _load_pos_data_fields(self, config):
        params = super()._load_pos_data_fields(config)
        params += ['l10n_ke_oscu_serial_number']
        return params
