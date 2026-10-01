from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _is_ci_fne_applicable(self, move):
        return move.l10n_ci_edi_is_needed

    def _get_all_extra_edis(self) -> dict:
        # EXTENDS 'account'
        res = super()._get_all_extra_edis()
        res.update({'ci_fne': {
            'label': self.env._("Send to FNE"),
            'is_applicable': self._is_ci_fne_applicable,
        }})
        return res

    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        # EXTENDS 'account'
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            if 'ci_fne' in invoice_data.get('extra_edis', {}):
                # Check for blocking validation messages
                validation_messages = (invoice.l10n_ci_edi_validation_messages or {}).values()
                if blocking := [msg for msg in validation_messages if msg.get('blocking')]:
                    invoice_data['error'] = {
                        'error_title': invoice.env._("Cannot send to FNE"),
                        'errors': [msg['message'] for msg in blocking],
                    }
                    continue

                _content, error = invoice._l10n_ci_edi_send()

                if error:
                    invoice_data['error'] = {
                        'error_title': invoice.env._("Failed to send to FNE"),
                        'errors': [error['message']],
                    }

                if self._can_commit():
                    self.env.cr.commit()
