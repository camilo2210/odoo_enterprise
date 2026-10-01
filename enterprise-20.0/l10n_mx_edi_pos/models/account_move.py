from odoo import api, models, Command


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('origin_payment_id')
    def _compute_l10n_mx_edi_payment_method_id(self):
        super()._compute_l10n_mx_edi_payment_method_id()
        for move in self:
            if payment_method := move.origin_payment_id.pos_payment_method_id.l10n_mx_edi_payment_method_id:
                move.l10n_mx_edi_payment_method_id = payment_method

    @api.depends("reversed_pos_order_id.l10n_mx_edi_document_ids.state")
    def _compute_l10n_mx_edi_document_ids(self):
        super()._compute_l10n_mx_edi_document_ids()
        for move in self:
            if move._l10n_mx_edi_is_cfdi_invoice_reversal():
                # Link auto-refund documents only (exclude invoice CFDIs).
                move.l10n_mx_edi_document_ids = [
                    Command.set(
                        move.reversed_pos_order_id.l10n_mx_edi_document_ids
                        .filtered(lambda doc: doc.state.startswith('invoice_') and not doc.move_id).ids
                    )
                ]

    @api.depends(
        "reversed_pos_order_id.l10n_mx_edi_document_ids.state",
        "reversed_pos_order_id.l10n_mx_edi_document_ids.sat_state",
    )
    def _compute_l10n_mx_edi_cfdi_state_and_attachment(self):
        super()._compute_l10n_mx_edi_cfdi_state_and_attachment()
        for move in self:
            if move._l10n_mx_edi_is_cfdi_invoice_reversal():
                # Filter to auto-refund documents only (exclude invoice CFDIs).
                documents = move.reversed_pos_order_id.l10n_mx_edi_document_ids.filtered(
                    lambda doc: not doc.move_id
                ).sorted()

                for doc in documents.filtered(lambda doc: doc.state in {
                    'invoice_sent',
                    'invoice_cancel',
                }):
                    if doc.sat_state != 'skip':
                        move.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                        break

                for doc in documents:
                    if doc.state == "invoice_sent":
                        move.l10n_mx_edi_cfdi_state = 'sent'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        break
                    if doc.state == 'invoice_cancel':
                        move.l10n_mx_edi_cfdi_state = 'cancel'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        move.l10n_mx_edi_invoice_cancellation_reason = doc.cancellation_reason
                        break

    def _l10n_mx_edi_is_cfdi_invoice_reversal(self):
        self.ensure_one()
        return self.reversed_pos_order_id and not self.reversed_pos_order_id.refunded_order_id
