# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def _get_tss_values(self):
        tss_values = super()._get_tss_values()
        if self.config_id.module_pos_restaurant:
            tss_values = [
                *tss_values,
                {
                    'name': "TSE-Erstbestellung",
                    'value': self.l10n_de_fiskaly_time_start,
                },
            ]
        return tss_values
