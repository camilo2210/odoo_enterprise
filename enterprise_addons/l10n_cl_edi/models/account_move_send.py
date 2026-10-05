from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _is_cl_edi_applicable(self, move):
        return move.l10n_cl_dte_status == 'not_sent'

    @api.model
    def _get_move_constraints(self, move):
        # EXTENDS 'account'. Allow sending CL vendor bills.
        constraints = super()._get_move_constraints(move) or {}
        if move.is_purchase_document() and self._is_cl_edi_applicable(move):
            constraints.pop('not_sale_document', None)
        return constraints

    def _get_all_extra_edis(self) -> dict:
        # EXTENDS 'account'
        res = super()._get_all_extra_edis()
        res.update({
            'cl_edi_sii': {
                'label': self.env._("Send to SII"),
                'is_applicable': self._is_cl_edi_applicable,
                'help': self.env._("Send the e-invoice data to SII."),
            },
        })
        return res

    # -------------------------------------------------------------------------
    # SENDING METHODS
    # -------------------------------------------------------------------------

    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        # EXTENDS 'account'
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            if 'cl_edi_sii' in invoice_data['extra_edis']:
                invoice.with_company(invoice.company_id).l10n_cl_send_dte_to_sii()
                if self._can_commit():
                    self.env.cr.commit()
