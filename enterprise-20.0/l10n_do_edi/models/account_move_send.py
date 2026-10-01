import logging
import requests

from markupsafe import Markup

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    # -------------------------------------------------------------------------
    # ATTACHMENTS
    # -------------------------------------------------------------------------

    def _get_placeholder_mail_attachments_data(self, move, invoice_edi_format=None, extra_edis=None, pdf_report=None):
        # EXTENDS 'account'
        res = super()._get_placeholder_mail_attachments_data(move, invoice_edi_format=invoice_edi_format, extra_edis=extra_edis, pdf_report=pdf_report)
        if 'do_dgii' in extra_edis and not move.l10n_do_edi_xml_file_id:
            filename = f"{move.name}.xml"
            res.append({
                'id': f'placeholder_{filename}',
                'name': filename,
                'mimetype': 'application/xml',
                'placeholder': True,
            })
        return res

    @api.model
    def _get_invoice_extra_attachments(self, move):
        """Override to only attach the signed xml for DO"""
        xml_attachment = move.l10n_do_edi_xml_file_id
        if xml_attachment and move.l10n_do_edi_state in ['infile_rejected']:
            xml_attachment = self.env['ir.attachment']
        return super()._get_invoice_extra_attachments(move) + xml_attachment

    @api.model
    def _l10n_do_edi_is_applicable(self, move):
        return move._l10n_do_edi_is_applicable() and not move.l10n_do_edi_state

    def _get_all_extra_edis(self):
        res = super()._get_all_extra_edis()
        res.update({'do_dgii': {'label': self.env._("DGII"), 'is_applicable': self._l10n_do_edi_is_applicable}})
        return res

    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        # Group invoices by company
        invoices_by_company = {}
        for invoice, invoice_data in invoices_data.items():
            if 'do_dgii' in invoice_data['extra_edis']:
                invoices_by_company.setdefault(invoice.company_id.root_id, {})[invoice] = invoice_data

        for company, company_invoices_data in invoices_by_company.items():
            # Retrieve access token per company
            access_token, token_error = self.env['account.move']._l10n_do_edi_get_infile_token(company)
            if token_error:
                for invoice, invoice_data in company_invoices_data.items():
                    invoice_data['error'] = {
                        'error_title': self.env._("Error authenticating with Infile:"),
                        'errors': [token_error],
                    }
                continue

            for invoice, invoice_data in company_invoices_data.items():
                if block_errors := invoice._l10n_do_edi_blocking_errors():
                    invoice_data['error'] = {
                        'error_title': self.env._('Error while generating the XML:'),
                        'errors': block_errors,
                    }
                    continue
                # Generate XML
                ecf_xml, ecf_error = invoice._l10n_do_edi_generate_ecf_xml(company)
                if ecf_error:
                    invoice_data['error'] = {
                        'error_title': self.env._('Error while generating the XML:'),
                        'errors': [ecf_error],
                    }
                    continue

                # Demo Mode
                if company.l10n_do_edi_web_service_env == 'demo':
                    unsigned_xml_attachment = invoice._l10n_do_edi_create_xml_attachment(ecf_xml, is_signed=False)
                    invoice.message_post(
                        body=Markup("<strong>%s</strong>") % self.env._("This is a DEMO response. The document was not sent to the DGII."),
                        attachment_ids=[unsigned_xml_attachment.id],
                    )
                    invoice['l10n_do_edi_state'] = 'dgii_accepted'
                    continue

                # Send the XML to Infile/DGII
                with requests.Session() as session:
                    response_json, unexpected_error = invoice._l10n_do_edi_send_xml_to_infile(company, access_token, ecf_xml, session)
                    if unexpected_error:
                        invoice_data['error'] = {
                            'error_title': self.env._("Error while sending invoice to DGII:"),
                            'errors': [unexpected_error],
                        }
                        continue
                    if not response_json:
                        invoice_data['error'] = {
                            'error_title': self.env._("Error while sending invoice to DGII:"),
                            'errors': [self.env._("Unknown error")],
                        }
                        continue

                # Process the xml response from Infile - either Infile rejected or accepted
                invoice._l10n_do_edi_process_xml_response(response_json, ecf_xml)
