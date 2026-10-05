# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        data['conditions']['l10n_at_cash_regid'] = bool(self.config_id.l10n_at_cash_regid)
        data['extra_data']['l10n_at_cash_regid'] = self.config_id.l10n_at_cash_regid
        if self.l10n_at_pos_order_receipt_qr_data:
            qr_code_data = 'data:image/png;base64,' + self.l10n_at_pos_order_receipt_qr_data
            data['image']['l10n_at_pos_order_receipt_qr_data'] = qr_code_data
        return data
