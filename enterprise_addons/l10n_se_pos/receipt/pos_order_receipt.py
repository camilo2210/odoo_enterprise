# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools.misc import format_datetime


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        data['conditions']['iot_fdm_se_id'] = self.config_id.iot_fdm_se_id

        if self.config_id.iot_fdm_se_id:
            name = "return" if self.is_refund_or_negative() else "receipt"
            name = "COPY" if self.is_reprint else name
            data['extra_data']['l10n_se_pos_type'] = name
            data['extra_data']['l10n_se_pos_original_date'] = format_datetime(self.env, self.create_date)

        return data
