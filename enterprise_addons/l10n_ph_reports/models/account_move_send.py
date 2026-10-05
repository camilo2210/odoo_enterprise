# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _get_move_constraints(self, move):
        constraints = super()._get_move_constraints(move)
        if move.l10n_ph_is_certificate_exportable:
            constraints.pop('not_sale_document', None)
        return constraints

    @api.model
    def _prepare_invoice_pdf_report(self, invoices_data):
        # EXTENDS 'account'
        certificates_data, remaining_data = {}, {}
        for invoice, invoice_data in invoices_data.items():
            group = certificates_data if invoice.l10n_ph_is_certificate_exportable else remaining_data
            group[invoice] = invoice_data

        if remaining_data:
            super()._prepare_invoice_pdf_report(remaining_data)

        for invoice, invoice_data in certificates_data.items():
            handler = self.env['l10n_ph.2306_2307.report.handler'].with_company(invoice.company_id)
            options = self.env.ref('l10n_ph_reports.2306_2307_report').with_company(invoice.company_id).get_options(previous_options={})
            result = handler._l10n_ph_generate_bill_certificate(invoice, options)
            if not result:
                invoice_data['error'] = {
                    'error_title': _("The withholding certificate could not be generated."),
                    'errors': [_("There is no withheld amount to certify for this bill.")],
                }
                continue

            filename, content = result
            # PH vendor bills do not have a dedicated send flow, so we reuse the
            # standard PDF attachment payload and store the certificate on
            # `invoice_pdf_report_file`. If bill sending is supported later, this
            # should be refactored to avoid overwriting the invoice report field.
            invoice_data['pdf_attachment_values'] = {
                'name': filename,
                'raw': content,
                'mimetype': 'application/pdf',
                'res_model': invoice._name,
                'res_id': invoice.id,
                'res_field': 'invoice_pdf_report_file',
            }
