from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = "pos.order.receipt"

    def order_receipt_generate_data(self, basic_receipt=False):
        # Extend l10n_co_pos
        data = super().order_receipt_generate_data(basic_receipt)

        if co_receipt_data := self.l10n_co_edi_pos_receipt_data:
            data['l10n_co_edi_pos'] = co_receipt_data

        return data
