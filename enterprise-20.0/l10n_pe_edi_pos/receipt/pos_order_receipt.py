from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)

        if self.company_id.country_code != 'PE' or not self.account_move:
            return data

        conditions = data['conditions']
        extra_data = data['extra_data']
        image = data['image']

        conditions['code_pe'] = True
        extra_data['report_name'] = self.account_move.l10n_latam_document_type_id.report_name
        extra_data['invoice_name'] = self.account_move.name
        if l10n_pe_edi_data := data['order'].get('l10n_pe_edi_data'):
            conditions['has_pe_edi_data'] = True
            image['l10n_pe_edi_pos_qrsrc'] = self._order_receipt_generate_qr_code(l10n_pe_edi_data['qr_str'])
            extra_data['summary'] = l10n_pe_edi_data['qr_str'].split("|")[-2]
            extra_data['amount_in_word'] = l10n_pe_edi_data['amount_to_text']

        return data
