from odoo import api, models
from odoo.tools import html2plaintext


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _is_pe_edi_applicable(self, move):
        return move.l10n_pe_edi_is_required and move.l10n_pe_edi_status != 'sent'

    def _get_all_extra_edis(self) -> dict:
        # EXTENDS 'account'
        res = super()._get_all_extra_edis()
        res.update({
            'pe_ubl_2_1': {
                'label': self.env._("Send to SUNAT"),
                'is_applicable': self._is_pe_edi_applicable,
                'help': self.env._("Send the e-invoice data to SUNAT."),
            },
        })
        return res

    # -------------------------------------------------------------------------
    # ALERTS
    # -------------------------------------------------------------------------

    def _get_alerts(self, moves, moves_data):
        # EXTENDS 'account'
        alerts = super()._get_alerts(moves, moves_data)

        pe_moves = moves.filtered(lambda m: 'pe_ubl_2_1' in moves_data[m]['extra_edis'])

        if len(pe_moves) == 1 and (pe_alerts := pe_moves._l10n_pe_edi_check_move_constraints()):
            alerts.update(pe_alerts)
        elif len(pe_moves) >= 2 and (pe_bad_moves := pe_moves.filtered(lambda m: m._l10n_pe_edi_check_move_constraints())):
            alerts['l10n_pe_edi_warning_not_ready_move'] = {
                'message': self.env._("The following invoice(s) are not ready to be sent to SUNAT:%s",
                             ''.join(f"\n- {move.display_name}" for move in pe_bad_moves)),
                'action_text': self.env._("View Invoice(s)"),
                'action': pe_bad_moves._get_records_action(name=self.env._("Check Invoice(s)")),
            }

        return alerts

    # -------------------------------------------------------------------------
    # ATTACHMENTS
    # -------------------------------------------------------------------------

    def _get_invoice_extra_attachments(self, move):
        # EXTENDS 'account'
        return super()._get_invoice_extra_attachments(move) + move.l10n_pe_edi_attachment_id

    def _get_placeholder_mail_attachments_data(self, move, invoice_edi_format=None, extra_edis=None, pdf_report=None):
        # EXTENDS 'account'
        results = super()._get_placeholder_mail_attachments_data(move, invoice_edi_format=invoice_edi_format, extra_edis=extra_edis, pdf_report=pdf_report)

        if not move.l10n_pe_edi_attachment_id and 'pe_ubl_2_1' in extra_edis:
            filename = move._l10n_pe_edi_generate_edi_filename() + '.zip'
            results = [{
                'id': f'placeholder_{filename}',
                'name': filename,
                'mimetype': 'application/zip',
                'placeholder': True,
            }]

        return results

    # -------------------------------------------------------------------------
    # SENDING METHODS
    # -------------------------------------------------------------------------

    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        # EXTENDS 'account'
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            # Not all invoices may need EDI.
            if 'pe_ubl_2_1' in invoice_data['extra_edis']:
                if api_error := invoice.with_company(invoice.company_id)._l10n_pe_edi_post_invoice():
                    invoice_data["error"] = {
                        "error_title": self.env._("Errors when submitting to SUNAT:"),
                        "errors": [html2plaintext(api_error.get('message'))],
                        # Worth an automatic retry by the send cron when SUNAT hasn't given us a
                        # definitive answer yet (like the CDR isn't generated yet), a genuine SUNAT
                        # rejection must not be retried forever.
                        "retry": api_error.get('retry', False),
                    }
