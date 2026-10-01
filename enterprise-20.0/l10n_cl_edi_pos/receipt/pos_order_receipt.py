# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools.misc import format_date


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        data['conditions']['code_cl'] = bool(self.company_id.country_id.code == 'CL')

        if self.company_id.country_id.code == 'CL':
            data['image']['l10n_cl_sii_barcode_image'] = self.account_move.l10n_cl_sii_barcode_image
            data['extra_data']['l10n_cl_edi_pos_tip'] = self._order_receipt_format_currency(self.amount_total * 0.10)
            data['extra_data']['l10n_latam_document_type_name'] = self.account_move.l10n_latam_document_type_id.name
            data['extra_data']['l10n_latam_document_number'] = self.account_move.l10n_latam_document_number
            label = dict(self.company_id._fields['l10n_cl_sii_regional_office']._description_selection(self.env)).get(self.company_id.l10n_cl_sii_regional_office)
            data['extra_data']['l10n_cl_sii_regional_office_name'] = label
            data['extra_data']['formatted_l10n_cl_dte_resolution_date'] = format_date(self.env, self.company_id['l10n_cl_dte_resolution_date'])

        return data
