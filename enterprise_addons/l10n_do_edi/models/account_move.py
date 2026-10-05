import datetime
import logging
import requests

from dateutil.parser import isoparse
from lxml import etree
from markupsafe import Markup
from urllib.parse import urlparse
from werkzeug.urls import url_encode

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL
from odoo.addons.account.tools import dict_to_xml
from odoo.addons.l10n_do_edi.tools import ecf_31, ecf_32, ecf_33, ecf_34

_logger = logging.getLogger(__name__)

ECF_TEMPLATES = {
    '31': ecf_31.ECF,
    '32': ecf_32.ECF,
    '33': ecf_33.ECF,
    '34': ecf_34.ECF,
}
ITBIS_TAX_INDICATOR_VALUES = {'1', '2', '3', '4'}


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_do_edi_income_type = fields.Selection(
        string="Income Type",
        selection=[
            ('01', 'Operational Income'),
            ('02', 'Financial Income'),
            ('03', 'Extraordinary Income'),
            ('04', 'Leasing Income'),
            ('05', 'Fixed Asset Sale Income'),
            ('06', 'Other Income'),
        ],
        default='01',
    )
    l10n_do_edi_state = fields.Selection(
        string="DO EDI Status",
        selection=[
            ('infile_accepted', 'Sent to DGII'),
            ('infile_rejected', 'Infile Rejected'),
            ('dgii_accepted', 'DGII Accepted'),
            ('dgii_rejected', 'DGII Rejected'),
        ],
        readonly=True,
        copy=False,
        tracking=True,
    )
    l10n_do_edi_last_status_check = fields.Datetime(
        string="Last Status Check",
        readonly=True,
        copy=False,
    )
    l10n_do_edi_modification_code = fields.Selection(
        string="Modification Code",
        selection=[
            ('1', 'Cancels the modified NCF'),
            ('2', 'Corrects the text in modified fiscal receipt'),
            ('3', 'Corrects the amounts of the modified NCF'),
        ],
    )
    l10n_do_edi_signature_datetime = fields.Datetime(
        string="Signature Date",
        readonly=True,
        copy=False,
    )
    l10n_do_edi_security_code = fields.Char(
        string="Security Code",
        readonly=True,
        copy=False,
    )
    l10n_do_edi_qr_url = fields.Char(
        string="DGII QR URL",
        readonly=True,
        copy=False,
    )
    l10n_do_edi_request_identifier = fields.Char(
        string="Request ID",
        readonly=True,
        copy=False,
    )
    l10n_do_edi_xml_file = fields.Binary(
        string="EDI XML File",
        attachment=True,
        copy=False,
    )
    l10n_do_edi_xml_file_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="EDI XML Attachment",
        compute=lambda self: self._compute_linked_attachment_id('l10n_do_edi_xml_file_id', 'l10n_do_edi_xml_file'),
        depends=['l10n_do_edi_xml_file'],
    )
    l10n_do_edi_warnings = fields.Json(compute="_compute_l10n_do_edi_warnings")

    def _l10n_do_edi_is_applicable(self):
        return self.country_code == 'DO' and self.l10n_latam_use_documents and self.l10n_latam_document_type_id

    # -------------------------------------------------------------------------
    # Compute methods
    # -------------------------------------------------------------------------
    @api.depends('l10n_do_edi_state')
    def _compute_show_reset_to_draft_button(self):
        """
        Override to show reset to draft button when the invoice has been accepted.
        Usually, with a rejection, the invoice can be resubmitted.
        """
        super()._compute_show_reset_to_draft_button()
        for move in self:
            if move.l10n_do_edi_state in ('infile_accepted', 'dgii_accepted'):
                move.show_reset_to_draft_button = False

    @api.depends('name')
    def _compute_l10n_latam_document_number(self):
        do_moves = self.filtered(lambda move: move._l10n_do_edi_is_applicable() and move.name and move.name != '/')
        prefix_length = 3
        for move in do_moves:
            move.l10n_latam_document_number = move.name[prefix_length:]
        super(AccountMove, self - do_moves)._compute_l10n_latam_document_number()

    @api.onchange('l10n_latam_document_type_id', 'l10n_latam_document_number', 'partner_id')
    def _inverse_l10n_latam_document_number(self):
        do_moves = self.filtered(lambda move: move._l10n_do_edi_is_applicable())
        for move in do_moves:
            if not move.l10n_latam_document_number:
                move.name = False
            else:
                move.name = "%s%s" % (move.l10n_latam_document_type_id.doc_code_prefix, move.l10n_latam_document_number)
        super(AccountMove, self - do_moves)._inverse_l10n_latam_document_number()

    @api.depends(
        'country_code', 'l10n_latam_use_documents', 'l10n_latam_document_type_id',
        'company_id', 'l10n_latam_document_internal_type', 'reversed_entry_id', 'debit_origin_id',
        'l10n_do_edi_modification_code', 'partner_id', 'invoice_line_ids.tax_ids',
    )
    def _compute_l10n_do_edi_warnings(self):
        """ Check for all the blocking errors before sending the invoice to DGII"""
        for move in self:
            if not move._l10n_do_edi_is_applicable():
                move.l10n_do_edi_warnings = False
                continue

            move.l10n_do_edi_warnings = {
                **move._l10n_do_edi_check_credentials(),
                **move._l10n_do_edi_check_document_range(),
                **move._l10n_do_edi_check_reference_document(),
                **move._l10n_do_edi_check_partner_vat(),
                **move._l10n_do_edi_check_invalid_tax_combo(),
                **move._l10n_do_edi_check_additional_taxes(),
                **move._l10n_do_edi_check_tax_price_include(),
                **move._l10n_do_edi_check_global_discount(),
            }

    # -------------------------------------------------------------------------
    # EDI Warning Checks
    # -------------------------------------------------------------------------
    def _l10n_do_edi_check_credentials(self):
        """Check that Infile credentials are configured when not in demo mode."""
        company_sudo = self.company_id.root_id.sudo()
        if company_sudo.l10n_do_edi_web_service_env == 'demo':
            return {}
        if not all([company_sudo.l10n_do_edi_username, company_sudo.l10n_do_edi_password,
                     company_sudo.l10n_do_edi_key, company_sudo.l10n_do_edi_llave]):
            return {
                "missing_credentials": {
                    "message": self.env._("Infile credentials are required for electronic invoicing."),
                    "action_text": self.env._("Please configure them in Accounting settings."),
                    "action": self.env.ref('account.action_account_config')._get_action_dict(),
                    "level": "danger",
                },
            }
        return {}

    def _l10n_do_edi_check_document_range(self):
        """Check that the document type has a valid, non-expired range configured."""
        doc_type = self.l10n_latam_document_type_id.with_company(self.company_id)
        doc_range = doc_type.l10n_do_edi_property_document_range_id
        warning_action_body = {
            "action_text": self.env._("Configure document type."),
                "action": {
                    **self.env.ref('l10n_latam_invoice_document.action_document_type')._get_action_dict(),
                    "res_id": doc_type.id,
                    "view_mode": "form",
                },
                "level": "danger",
        }
        if not doc_range:
            return {
                "missing_document_range": {
                    "message": self.env._("No authorized sequence range is configured for document type %s.", doc_type.display_name),
                    **warning_action_body,
                },
            }
        if doc_type.code in ('31', '33') and not doc_range.expiration_date:
            return {
                "missing_expiration_date": {
                    "message": self.env._("The expiration date for the document range of %s is required.", doc_type.display_name),
                    **warning_action_body,
                },
            }
        if doc_range.expiration_date and fields.Date.context_today(self) > doc_range.expiration_date:
            return {
                "expired_document_range": {
                    "message": self.env._(
                        "The document range for %(doc_type)s has expired on %(date)s. Please update the range.",
                        doc_type=doc_type.display_name,
                        date=doc_range.expiration_date,
                    ),
                    **warning_action_body,
                },
            }
        return {}

    def _l10n_do_edi_check_reference_document(self):
        """Check that credit/debit notes reference the original document and have a modification code."""
        doc_code = self.l10n_latam_document_type_id.code
        res = {}
        if doc_code == '33' and not self.debit_origin_id:
            res["missing_debit_origin"] = {
                "message": self.env._("Debit Notes (type 33) must reference the original Customer Invoice. Please create the Debit Note from the original invoice."),
                "level": "danger",
            }
        if doc_code == '34' and not self.reversed_entry_id:
            res["missing_reversed_entry"] = {
                "message": self.env._("Credit Notes (type 34) must reference the original Customer Invoice. Please create the Credit Note from the original invoice."),
                "level": "danger",
            }
        if doc_code in ('33', '34') and not self.l10n_do_edi_modification_code:
            res["missing_modification_code"] = {
                "message": self.env._("A modification code is required for Credit and Debit Notes."),
                "level": "danger",
            }
        return res

    def _l10n_do_edi_check_partner_vat(self):
        """Check that partners have their RNC set."""
        min_amount_total_signed = 250000
        if self.partner_id and not self.partner_id._l10n_do_has_rnc() and (self.amount_total_signed >= min_amount_total_signed or self.l10n_latam_document_type_id_code == '31'):
            return {
                "missing_partner_vat": {
                    "message": self.env._(
                        "The partner %(partner)s does not have an RNC set. It is required if the document type is 31 or the total amount is greater than or equal to RD$ %(min_amount)s.",
                        partner=self.partner_id.display_name,
                        min_amount=min_amount_total_signed,
                    ),
                    "level": "danger",
                },
            }
        return {}

    def _l10n_do_edi_check_invalid_tax_combo(self):
        """
        Check that no invoice line has more than one tax with an invoicing indicator in (1-4).
        Only one such tax is allowed per line — whether with distinct or identical indicators.
        """
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            matching_taxes = line.tax_ids.filtered(lambda t: t.l10n_do_edi_invoicing_indicator in ITBIS_TAX_INDICATOR_VALUES)
            if len(matching_taxes) > 1:
                return {
                    "mixed_invoicing_indicators": {
                        "message": self.env._("Line '%(line)s' has an invalid combination of taxes: %(taxes)s. They cannot be set on the same line.",
                            line=line.name,
                            taxes=', '.join(matching_taxes.mapped('name')),
                        ),
                        "level": "danger",
                    },
                }
        return {}

    def _l10n_do_edi_check_additional_taxes(self):
        """Check that either all or no invoice lines have additional taxes"""
        product_lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        has_additional = [any(t.l10n_do_edi_invoicing_indicator == '7' for t in line.tax_ids) for line in product_lines]
        if any(has_additional) and not all(has_additional):
            return {
                "inconsistent_additional_taxes": {
                    "message": self.env._("Either all or no invoice lines must have additional taxes."),
                    "level": "danger",
                },
            }
        return {}

    def _l10n_do_edi_check_tax_price_include(self):
        """Check that all taxes on invoice lines are either all price-included or all price-excluded."""
        product_lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        price_included = [tax.price_include for line in product_lines for tax in line.tax_ids if tax.l10n_do_edi_invoicing_indicator in ITBIS_TAX_INDICATOR_VALUES]
        if any(price_included) and not all(price_included):
            return {
                "mixed_price_include_taxes": {
                    "message": self.env._("All ITBIS taxes on invoice lines must be either all price-included or all price-excluded."),
                    "level": "danger",
                },
            }
        return {}

    def _l10n_do_edi_check_global_discount(self):
        """Check that the invoice does not contain negative lines (global discounts)."""
        if any(
            line.quantity < 0 or line.price_total < 0
            for line in self.invoice_line_ids
            if line.display_type not in ('line_section', 'line_subsection', 'line_note')
        ):
            return {
                "global_discount_not_supported": {
                    "message": self.env._("Global discounts are not supported for Dominican Republic electronic invoicing."),
                    "level": "danger",
                },
            }
        return {}

    def _l10n_do_edi_blocking_errors(self):
        """Return only 'danger' level errors that should block EDI submission."""
        return [error['message'] for error in (self.l10n_do_edi_warnings or {}).values() if error.get('level') == 'danger']

    # -------------------------------------------------------------------------
    # Report
    # -------------------------------------------------------------------------
    def _get_name_invoice_report(self):
        self.ensure_one()
        if self._l10n_do_edi_is_applicable():
            return 'l10n_do_edi.report_invoice_document'
        return super()._get_name_invoice_report()

    # -------------------------------------------------------------------------
    # Sequence Mixin Methods
    # -------------------------------------------------------------------------
    def _l10n_do_edi_get_formatted_sequence(self, number):
        """Return the specific invoice sequence format for DO"""
        return "%s%010d" % (self.l10n_latam_document_type_id.doc_code_prefix, number)

    def _get_starting_sequence(self):
        """
        Override to format the starting sequence specific to DO
        Default sequence num to 0 if no document range is configured
        """
        if self._l10n_do_edi_is_applicable():
            if doc_range := self.l10n_latam_document_type_id.with_company(self.company_id).l10n_do_edi_property_document_range_id:
                return self._l10n_do_edi_get_formatted_sequence(doc_range.start_number - 1)
            return self._l10n_do_edi_get_formatted_sequence(0)
        return super()._get_starting_sequence()

    def _get_last_sequence_domain(self, relaxed=False):
        """Override to build the domain to find the last sequence across all journals"""
        condition = super()._get_last_sequence_domain(relaxed)
        if self.country_code == "DO" and self.l10n_latam_use_documents:
            t = condition._sql_tuple
            code = t[0].replace('journal_id = %s AND', '%s IS NOT NULL AND')
            condition = SQL(code, *t[1], to_flush=t[2])  # pylint: disable=sql-injection
            condition = SQL(
                "%s AND l10n_latam_document_type_id = %s AND company_id = %s AND move_type IN ('out_invoice', 'out_refund')",
                condition,
                self.l10n_latam_document_type_id.id or 0,
                self.company_id.id or None,
            )
        return condition

    def _get_last_sequence(self, relaxed=False, with_prefix=None):
        """
        Override to find the last sequence in the case that
        the user changes the starting number of the document type range
        to a higher number
        """
        last_sequence = super()._get_last_sequence(relaxed, with_prefix)
        if self._l10n_do_edi_is_applicable():
            if not last_sequence:
                last_sequence = self._get_starting_sequence()  # New start
            else:
                last_sequence = max(last_sequence, self._get_starting_sequence())
        return last_sequence

    # -------------------------------------------------------------------------
    # Infile Requests Methods
    # -------------------------------------------------------------------------
    @api.model
    def _l10n_do_edi_format_response_error(self, title, response):
        """Return the formatted error message given a title and a response object"""
        return f"{title}: {response.url}\nHTTP {response.status_code}: {response.reason}\nBody: {response.text}"

    @api.model
    def _l10n_do_edi_get_infile_url(self, infile_env, url_type):
        """ Return the url based on the environment and type of request"""
        base_url = f"https://fe-webservice{'-test' if infile_env == 'test' else ''}.infile.com.do/republica_dominicana"
        url_dict = {
            'login': f"{base_url}/auth/login",
            'ecf': f"{base_url}/api/v1/emision/ecf",
            'dgii': f"{base_url}/api/v1/consultas/ecf",
        }
        return url_dict[url_type]

    @api.model
    def _l10n_do_edi_get_infile_token(self, company):
        """
        Retrieve the access token from Infile via basic auth.
        :return: tuple (token, error) where error is None on success
        """
        infile_env = company.sudo().l10n_do_edi_web_service_env
        if infile_env == 'demo':
            return '', None
        username = company.sudo().l10n_do_edi_username
        password = company.sudo().l10n_do_edi_password
        headers = {
            'Security-Key': company.sudo().l10n_do_edi_key,
        }
        data = {
            'rnc': company.sudo().vat,
            'llave': company.sudo().l10n_do_edi_llave,
        }
        login_url = self._l10n_do_edi_get_infile_url(infile_env, 'login')

        try:
            response = requests.post(login_url, auth=(username, password), headers=headers, data=data, timeout=20)
        except requests.exceptions.RequestException as e:
            _logger.exception("Failed to get Infile token for company, %s", company.name)
            return '', str(e)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            _logger.exception(self._l10n_do_edi_format_response_error(f"Failed to get Infile token for company, {company.name}", response))
            return '', str(e)

        try:
            response_json = response.json()
        except ValueError:
            return '', self.env._("Infile returned an invalid response when requesting for access token.")

        return response_json['token'], None

    @api.model
    def _l10n_do_edi_send_xml_to_infile(self, company, access_token, ecf_xml, session):
        """
        Send the XML to Infile and return the response.
        :return: tuple (response_json, error) where error is None on success
        """
        infile_env = company.l10n_do_edi_web_service_env
        if infile_env == 'demo':
            return {}, None
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/xml',
        }
        url = self._l10n_do_edi_get_infile_url(infile_env, 'ecf')

        try:
            response = session.post(url, headers=headers, data=ecf_xml, timeout=20)
        except requests.exceptions.RequestException as e:
            _logger.exception("Failed to send XML from Infile")
            return {}, str(e)

        try:
            response_json = response.json()
        except ValueError:
            return {}, self.env._("Infile returned an invalid response when sending the xml.")

        return response_json, None

    def _l10n_do_edi_request_dgii_status(self, company, access_token, session=None):
        """Request the DGII status of the invoice through Infile and return the response"""
        self.ensure_one()
        self.l10n_do_edi_last_status_check = fields.Datetime.now()

        infile_env = company.sudo().l10n_do_edi_web_service_env
        if infile_env == 'demo':
            return {}, None
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f"{self._l10n_do_edi_get_infile_url(infile_env, 'dgii')}?{url_encode({'solicitud_id': self.l10n_do_edi_request_identifier})}"

        try:
            response = (session or requests).get(url, headers=headers, timeout=20)
        except requests.exceptions.RequestException as e:
            _logger.exception("Failed to get DGII status from Infile for %s", url)
            return {}, self.env._("Failed to get DGII status from Infile: %s", e)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            return {}, self.env._("Failed to get DGII status from Infile: %s", e)

        try:
            response_json = response.json()
        except ValueError:
            return {}, self.env._("Infile returned an invalid response when requesting the DGII status.")

        return response_json, None

    # -------------------------------------------------------------------------
    # Response Processing Methods
    # -------------------------------------------------------------------------
    def _l10n_do_edi_create_xml_attachment(self, ecf_xml, is_signed):
        """Create an XML attachment for the record, stored on the l10n_do_edi_xml_file binary field."""
        self.ensure_one()
        name = f'{self.name}.xml' if is_signed else f'{self.name}_unsigned.xml'
        attachment = self.env['ir.attachment'].create({
            'name': name,
            'raw': ecf_xml,
            'mimetype': 'application/xml',
            'res_model': 'account.move',
            'res_id': self.id,
            'res_field': 'l10n_do_edi_xml_file',
        })
        self.invalidate_recordset(fnames=['l10n_do_edi_xml_file', 'l10n_do_edi_xml_file_id'])
        return attachment

    def _l10n_do_edi_process_dgii_status_response(self, response_json):
        """Process the DGII status response and set l10n_do_edi_state accordingly"""
        self.ensure_one()
        consulta = response_json.get('consulta', {})
        dgii_code = consulta.get('consulta_dgii_codigo')
        if dgii_code in ['1', '4']:
            self.l10n_do_edi_state = 'dgii_accepted'
        elif dgii_code == '2':
            self.l10n_do_edi_state = 'dgii_rejected'
            self.message_post(
                body=Markup("<b>%(title)s</b><ul>%(errors)s</ul>") % {
                    'title': self.env._("Errors from DGII:"),
                    'errors': Markup('').join(Markup('<li>%s</li>') % e['valor'] for e in consulta['consulta_dgii_respuesta']),
                },
            )
        elif dgii_code == '3':
            self.message_post(
                body=Markup("%s") % self.env._("DGII is still processing the invoice, please try again later."),
            )

    def _l10n_do_edi_get_signed_xml(self, infile_xml_url, ecf_xml):
        """
        Return the attachment of the downloaded signed xml from Infile
        or the generated unsigned xml as backup
        """
        self.ensure_one()
        infile_env = self.company_id.l10n_do_edi_web_service_env
        expected_host = urlparse(self._l10n_do_edi_get_infile_url(infile_env, 'ecf')).hostname
        incoming_host = urlparse(infile_xml_url).hostname
        if incoming_host != expected_host:
            _logger.warning("Refusing to fetch signed XML from untrusted host %s for invoice %s", incoming_host, self.name)
            return [self._l10n_do_edi_create_xml_attachment(ecf_xml, is_signed=False).id]

        try:
            signed_xml_response = requests.get(infile_xml_url, timeout=30)
        except requests.exceptions.RequestException:
            _logger.exception("Failed to download signed XML from Infile for invoice %s from %s", self.name, infile_xml_url)
            unsigned_xml_attachment = self._l10n_do_edi_create_xml_attachment(ecf_xml, is_signed=False)
            return [unsigned_xml_attachment.id]

        try:
            signed_xml_response.raise_for_status()
        except requests.exceptions.HTTPError:
            unsigned_xml_attachment = self._l10n_do_edi_create_xml_attachment(ecf_xml, is_signed=False)
            return [unsigned_xml_attachment.id]

        signed_xml_attachment = self._l10n_do_edi_create_xml_attachment(signed_xml_response.content, is_signed=True)
        return [signed_xml_attachment.id]

    def _l10n_do_edi_process_xml_response(self, response_json, ecf_xml):
        """
        Process the response from Infile after sending the xml
        - Error: Set the state to 'infile_rejected'
        - Success: Set the state to 'infile_accepted' along with other fields required necessary
        for future requests.
        - Log and attach the xml in the chatter
        """
        self.ensure_one()
        if not response_json['resultado']:
            self.l10n_do_edi_state = 'infile_rejected'
            errors = [error['descripcion'] for error in response_json.get('errores', [])]
            unsigned_xml_attachment = self._l10n_do_edi_create_xml_attachment(ecf_xml, is_signed=False)
            self.message_post(
                body=Markup(
                    "%(title)s"
                    "<ul>"
                    "<li>%(request_id_label)s: %(request_id)s</li>"
                    "<li>%(environment_label)s: %(environment)s</li>"
                    "<li>%(errors_label)s: <ul>%(errors)s</ul></li>"
                    "</ul>"
                ) % {
                    'title': self.env._("Error while sending invoice to DGII:"),
                    'request_id_label': self.env._("Request ID"),
                    'request_id': response_json['solicitud_id'],
                    'environment_label': self.env._("Environment"),
                    'environment': response_json['ambiente'],
                    'errors_label': self.env._("Errors"),
                    'errors': Markup('').join(Markup('<li>%s</li>') % e for e in errors),
                },
                attachment_ids=[unsigned_xml_attachment.id],
            )
            return

        self.write({
            'l10n_do_edi_qr_url': response_json['url_qr_consulta_dgii'],
            'l10n_do_edi_security_code': response_json['codigo_seguridad'],
            'l10n_do_edi_state': 'infile_accepted',
            'l10n_do_edi_signature_datetime': isoparse(response_json['fecha']).astimezone(datetime.UTC).replace(tzinfo=None),
            'l10n_do_edi_request_identifier': response_json['solicitud_id'],
        })

        infile_pdf_url = response_json['url_pdf']
        infile_xml_url = infile_pdf_url.replace('formato=pdf', 'formato=xml')
        attachment_ids = self._l10n_do_edi_get_signed_xml(infile_xml_url, ecf_xml)

        self.message_post(
            body=Markup(
                "%(title)s"
                "<ul>"
                "<li>%(request_id_label)s: %(request_id)s</li>"
                "<li>%(environment_label)s: %(environment)s</li>"
                "<li>%(track_id_label)s: %(track_id)s</li>"
                "<li>%(security_code_label)s: %(security_code)s</li>"
                "<li>%(pdf_url_label)s: <a href='%(pdf_url)s'>%(pdf_url)s</a></li>"
                "<li>%(qr_url_label)s: <a href='%(qr_url)s'>%(qr_url)s</a></li>"
                "<li>%(signed_xml_url_label)s: <a href='%(signed_xml_url)s'>%(signed_xml_url)s</a></li>"
                "</ul>"
            ) % {
                'title': self.env._("Invoice accepted by Infile and sent to DGII:"),
                'request_id_label': self.env._("Request ID"),
                'request_id': response_json['solicitud_id'],
                'environment_label': self.env._("Environment"),
                'environment': response_json['ambiente'],
                'track_id_label': self.env._("Track ID"),
                'track_id': response_json['trackid'],
                'security_code_label': self.env._("Security Code"),
                'security_code': response_json['codigo_seguridad'],
                'pdf_url_label': self.env._("PDF URL"),
                'pdf_url': infile_pdf_url,
                'qr_url_label': self.env._("QR URL"),
                'qr_url': response_json['url_qr_consulta_dgii'],
                'signed_xml_url_label': self.env._("Signed XML URL"),
                'signed_xml_url': infile_xml_url,
            },
            attachment_ids=attachment_ids,
        )

    # -------------------------------------------------------------------------
    # Buttons
    # -------------------------------------------------------------------------
    def _get_fields_to_detach(self):
        # EXTENDS 'account'
        fields_list = super()._get_fields_to_detach()
        fields_list.append('l10n_do_edi_xml_file')
        return fields_list

    def button_draft(self):
        res = super().button_draft()
        self.filtered('l10n_do_edi_state').write({
            'l10n_do_edi_state': False,
            'l10n_do_edi_signature_datetime': False,
            'l10n_do_edi_security_code': False,
            'l10n_do_edi_qr_url': False,
            'l10n_do_edi_request_identifier': False,
        })
        return res

    def action_l10n_do_edi_request_dgii_status(self):
        """Button action to request the DGII status of the invoice"""
        self.ensure_one()
        company = self.company_id.root_id
        access_token, token_error = self._l10n_do_edi_get_infile_token(company)
        if token_error:
            raise UserError(token_error)
        response_json, error = self._l10n_do_edi_request_dgii_status(company, access_token)
        if error:
            raise UserError(error)
        self._l10n_do_edi_process_dgii_status_response(response_json)

    # -------------------------------------------------------------------------
    # Cron
    # -------------------------------------------------------------------------

    def _cron_l10n_do_edi_update_dgii_status(self):
        """Cron job to check DGII status for invoices accepted by Infile."""
        domain = [
            ('l10n_do_edi_state', '=', 'infile_accepted'),
            ('state', '=', 'posted'),
            '|',
                ('l10n_do_edi_last_status_check', '=', False),
                ('l10n_do_edi_last_status_check', '<=', 'now -1d'),
        ]
        invoices = self.search(domain)
        self.env['ir.cron']._commit_progress(remaining=len(invoices))

        for company, company_invoices in invoices.grouped(lambda inv: inv.company_id.root_id).items():
            company_invoices_len = len(company_invoices)
            if company.l10n_do_edi_web_service_env == 'demo':
                if not self.env['ir.cron']._commit_progress(company_invoices_len):
                    return
                continue

            company_invoices = company_invoices.try_lock_for_update()
            if not company_invoices:
                if not self.env['ir.cron']._commit_progress(company_invoices_len):
                    return
                continue

            access_token, token_error = self._l10n_do_edi_get_infile_token(company)
            if token_error:
                if not self.env['ir.cron']._commit_progress(company_invoices_len):
                    return
                continue

            with requests.Session() as session:
                for invoice in company_invoices:
                    response_json, error = invoice._l10n_do_edi_request_dgii_status(company, access_token, session)
                    if error:
                        if not self.env['ir.cron']._commit_progress(1):
                            return
                        continue
                    invoice._l10n_do_edi_process_dgii_status_response(response_json)
                    if not self.env['ir.cron']._commit_progress(1):
                        return

    # -------------------------------------------------------------------------
    # ECF XML Generation
    # -------------------------------------------------------------------------
    def _l10n_do_edi_get_id_doc_node(self):
        """Return the IdDoc node"""
        doc_range = self.l10n_latam_document_type_id.with_company(self.company_id).l10n_do_edi_property_document_range_id
        expiration_date = doc_range.expiration_date
        return {
            'TipoeCF': {'_text': self.l10n_latam_document_type_id_code},
            'eNCF': {'_text': self.name},
            'FechaVencimientoSecuencia': {'_text': expiration_date.strftime('%d-%m-%Y')} if expiration_date and self.l10n_latam_document_type_id_code in ['31', '33'] else {},
            'IndicadorNotaCredito': {'_text': "1" if self.reversed_entry_id.invoice_date > fields.Date.context_today(self) + datetime.timedelta(days=30) else "0"}
                if self.l10n_latam_document_type_id_code == '34' else {},
            # assuming the invoice lines will all be tax included or excluded from _l10n_do_edi_check_tax_price_include
            'IndicadorMontoGravado': {'_text': '1' if any(t.price_include for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product') for t in line.tax_ids) else '0'},
            'TipoIngresos': {'_text': self.l10n_do_edi_income_type},
            'TipoPago': {'_text': '1' if self.invoice_date == self.invoice_date_due else '2'},
            'FechaLimitePago': {'_text': self.invoice_date_due.strftime('%d-%m-%Y')} if self.invoice_date != self.invoice_date_due else {},
        }

    def _l10n_do_edi_get_comprador_node(self):
        """Return the Comprador node"""
        is_foreign_partner = self.partner_id.country_code != 'DO'
        include_foreign_partners = self.l10n_latam_document_type_id_code != '31'
        return {
            'RNCComprador': {'_text': self.partner_id.vat} if not is_foreign_partner else {},
            'IdentificadorExtranjero': {'_text': self.partner_id.vat} if is_foreign_partner and include_foreign_partners else {},  # AlfNum20Type -> don't format since it's VAT
            'RazonSocialComprador': {'_text': self.partner_id.name[:150]},  # AlfNum150Type
        }

    def _l10n_do_edi_get_additional_tax_by_code_vals(self, base_lines):
        """Return the dict of aggregated base lines based on the additional tax code"""
        def grouping_function(base_line, tax_data):
            return tax_data and tax_data['tax'].l10n_do_edi_additional_tax_code
        base_lines_aggregated = self.env['account.tax']._aggregate_base_lines_tax_details(base_lines, grouping_function)
        return self.env['account.tax']._aggregate_base_lines_aggregated_values(base_lines_aggregated)

    def _l10n_do_edi_get_impuestos_adicionales_node(self, base_lines):
        """Return the formatted ImpuestosAdicionales XML node"""
        additional_tax_vals = self._l10n_do_edi_get_additional_tax_by_code_vals(base_lines)
        return {'ImpuestoAdicional': [
            {
                'TipoImpuesto': {'_text': code},
                'TasaImpuestoAdicional': {'_text': f'{(vals['raw_tax_amount'] / vals['raw_total_excluded']) * 100:.2f}'},
                'OtrosImpuestosAdicionales': {'_text': f'{vals['raw_tax_amount']:.2f}'},
            }
            for code, vals in additional_tax_vals.items() if code
        ]}

    def _l10n_do_edi_get_impuestos_adicionales_otra_moneda_node(self, base_lines):
        """Return the formatted ImpuestosAdicionalesOtraMoneda XML node"""
        additional_tax_vals = self._l10n_do_edi_get_additional_tax_by_code_vals(base_lines)
        return {'ImpuestoAdicionalOtraMoneda': [
            {
                'TipoImpuestoOtraMoneda': {'_text': code},
                'TasaImpuestoAdicionalOtraMoneda': {'_text': f'{(vals['raw_tax_amount_currency'] / vals['raw_total_excluded_currency']) * 100:.2f}'},
                'OtrosImpuestosAdicionalesOtraMoneda': {'_text': f'{vals['raw_tax_amount_currency']:.2f}'},
            }
            for code, vals in additional_tax_vals.items() if code
        ]}

    def _l10n_do_edi_get_totales_vals(self, base_lines, is_foreign_currency=False):
        """Return a dict of computed totals used in Totales/OtraMoneda node"""

        # Aggregate by invoicing indicator
        def grouping_function(base_line, tax_data):
            return tax_data and tax_data['tax'].l10n_do_edi_invoicing_indicator
        # A list of tuple <base_line, results> that associates the result for each base line independently
        base_lines_aggregated = self.env['account.tax']._aggregate_base_lines_tax_details(base_lines, grouping_function)
        # Aggregate the values returned by '_aggregate_base_lines_tax_details' for the whole invoice with indicators as keys
        totals_by_indicator = self.env['account.tax']._aggregate_base_lines_aggregated_values(base_lines_aggregated)

        def get_amount(indicator, amount_type):
            return totals_by_indicator.get(indicator, {}).get(amount_type, 0.0)

        # Build base and tax amounts per indicator
        vals = {}
        base_keys = {
            '1': 'monto_gravado_i1', '2': 'monto_gravado_i2', '3': 'monto_gravado_i3',
            '4': 'monto_exento', None: 'monto_no_facturable',
        }
        tax_keys = {
            '1': 'total_itbis1', '2': 'total_itbis2', '3': 'total_itbis3',
            '5': 'monto_itbis_retenido', '6': 'monto_isr_retenido', '7': 'monto_impuesto_adicional',
        }
        for indicator, key in base_keys.items():
            vals[key] = get_amount(indicator, 'raw_base_amount' if not is_foreign_currency else 'raw_base_amount_currency')
        for indicator, key in tax_keys.items():
            vals[key] = get_amount(indicator, 'raw_tax_amount' if not is_foreign_currency else 'raw_tax_amount_currency')

        # Computed totals
        vals['monto_gravado_total'] = vals['monto_gravado_i1'] + vals['monto_gravado_i2'] + vals['monto_gravado_i3']
        vals['total_itbis'] = vals['total_itbis1'] + vals['total_itbis2'] + vals['total_itbis3']
        vals['monto_total'] = vals['monto_gravado_total'] + vals['monto_exento'] + vals['total_itbis'] + vals['monto_impuesto_adicional']

        return vals

    def _l10n_do_edi_get_totales_node(self, base_lines, include_withholdings):
        """
        Return the Totales XML node
        :param include_withholdings bool            : a boolean indicating whether the document type includes withholdings
        """
        totales_vals = self._l10n_do_edi_get_totales_vals(base_lines)
        return {
            'MontoGravadoTotal': {'_text': f'{totales_vals.get("monto_gravado_total"):.2f}'} if totales_vals.get('monto_gravado_total') else {},
            'MontoGravadoI1': {'_text': f'{totales_vals.get("monto_gravado_i1"):.2f}'} if totales_vals.get('monto_gravado_i1') else {},
            'MontoGravadoI2': {'_text': f'{totales_vals.get("monto_gravado_i2"):.2f}'} if totales_vals.get('monto_gravado_i2') else {},
            'MontoGravadoI3': {'_text': f'{totales_vals.get("monto_gravado_i3"):.2f}'} if totales_vals.get('monto_gravado_i3') else {},
            'MontoExento': {'_text': f'{totales_vals.get("monto_exento"):.2f}'} if totales_vals.get('monto_exento') else {},
            'ITBIS1': {'_text': '18'} if totales_vals.get('monto_gravado_i1') else {},
            'ITBIS2': {'_text': '16'} if totales_vals.get('monto_gravado_i2') else {},
            'ITBIS3': {'_text': '0'} if totales_vals.get('monto_gravado_i3') else {},
            'TotalITBIS': {'_text': f'{totales_vals.get("total_itbis"):.2f}'} if totales_vals.get('total_itbis') else {},
            'TotalITBIS1': {'_text': f'{totales_vals.get("total_itbis1"):.2f}'} if totales_vals.get('total_itbis1') else {},
            'TotalITBIS2': {'_text': f'{totales_vals.get("total_itbis2"):.2f}'} if totales_vals.get('total_itbis2') else {},
            'TotalITBIS3': {'_text': f'{totales_vals.get("total_itbis3"):.2f}'} if totales_vals.get('monto_gravado_i3') else {},  # Send if ITBIS 0% tax was applied
            'MontoImpuestoAdicional': {'_text': f'{totales_vals.get("monto_impuesto_adicional"):.2f}'} if totales_vals.get('monto_impuesto_adicional') else {},
            'ImpuestosAdicionales': self._l10n_do_edi_get_impuestos_adicionales_node(base_lines) if totales_vals.get('monto_impuesto_adicional') else {},
            'MontoTotal': {'_text': f'{totales_vals.get("monto_total"):.2f}'},
            'MontoNoFacturable': {'_text': f'{totales_vals.get("monto_no_facturable"):.2f}'} if totales_vals.get('monto_no_facturable') else {},
            'TotalITBISRetenido': {'_text': f'{-totales_vals.get("monto_itbis_retenido"):.2f}'}
                if totales_vals.get('monto_itbis_retenido') and include_withholdings else {},
            'TotalISRRetencion': {'_text': f'{-totales_vals.get("monto_isr_retenido"):.2f}'}
                if totales_vals.get('monto_isr_retenido') and include_withholdings else {},
        }

    def _l10n_do_edi_get_otra_moneda_node(self, base_lines):
        """Return the OtraMoneda node if currency != DOP"""
        node = {}
        if self.currency_id != self.env.ref('base.DOP'):
            totales_vals = self._l10n_do_edi_get_totales_vals(base_lines, is_foreign_currency=True)
            rate = 1 / self.invoice_currency_rate
            node = {
                'TipoMoneda': {'_text': self.currency_id.name},
                'TipoCambio': {'_text': f'{rate:.4f}'},
                'MontoGravadoTotalOtraMoneda': {'_text': f'{totales_vals.get("monto_gravado_total"):.2f}'} if totales_vals.get('monto_gravado_total') else {},
                'MontoGravado1OtraMoneda': {'_text': f'{totales_vals.get("monto_gravado_i1"):.2f}'} if totales_vals.get('monto_gravado_i1') else {},
                'MontoGravado2OtraMoneda': {'_text': f'{totales_vals.get("monto_gravado_i2"):.2f}'} if totales_vals.get('monto_gravado_i2') else {},
                'MontoGravado3OtraMoneda': {'_text': f'{totales_vals.get("monto_gravado_i3"):.2f}'} if totales_vals.get('monto_gravado_i3') else {},
                'MontoExentoOtraMoneda': {'_text': f'{totales_vals.get("monto_exento"):.2f}'} if totales_vals.get('monto_exento') else {},
                'TotalITBISOtraMoneda': {'_text': f'{totales_vals.get("total_itbis"):.2f}'} if totales_vals.get('total_itbis') else {},
                'TotalITBIS1OtraMoneda': {'_text': f'{totales_vals.get("total_itbis1"):.2f}'} if totales_vals.get('total_itbis1') else {},
                'TotalITBIS2OtraMoneda': {'_text': f'{totales_vals.get("total_itbis2"):.2f}'} if totales_vals.get('total_itbis2') else {},
                'TotalITBIS3OtraMoneda': {'_text': f'{totales_vals.get("total_itbis3"):.2f}'} if totales_vals.get('monto_gravado_i3') else {},
                'MontoImpuestoAdicionalOtraMoneda': {'_text': f'{totales_vals.get("monto_impuesto_adicional"):.2f}'} if totales_vals.get('monto_impuesto_adicional') else {},
                'ImpuestosAdicionalesOtraMoneda': self._l10n_do_edi_get_impuestos_adicionales_otra_moneda_node(base_lines) if totales_vals.get('monto_impuesto_adicional') else {},
                'MontoTotalOtraMoneda': {'_text': f'{totales_vals.get("monto_total"):.2f}'},
            }
        return node

    def _l10n_do_edi_get_retencion_node(self, taxes_data):
        """
        Return the Retencion node if there are any taxes
        whose invoicing indicator is 5 or 6 (withholdings)
        :param taxes_data [dict]
        """
        node = {}
        if retencion_taxes_data := [td for td in taxes_data if td['tax'].l10n_do_edi_invoicing_indicator in ('5', '6')]:
            monto_itbis_retenido = 0.0
            monto_isr_retenido = 0.0
            for tax_data in retencion_taxes_data:
                raw_tax_amount = -tax_data['raw_tax_amount']
                if tax_data['tax'].l10n_do_edi_invoicing_indicator == '5':
                    monto_itbis_retenido += raw_tax_amount
                elif tax_data['tax'].l10n_do_edi_invoicing_indicator == '6':
                    monto_isr_retenido += raw_tax_amount

            node.update({
                'IndicadorAgenteRetencionoPercepcion': {'_text': '1'},
                'MontoITBISRetenido': {'_text': f'{monto_itbis_retenido:.2f}'} if monto_itbis_retenido else {},
                'MontoISRRetenido': {'_text': f'{monto_isr_retenido:.2f}'} if monto_isr_retenido else {},
            })
        return node

    def _l10n_do_edi_get_items_node(self, base_lines, include_withholdings):
        """Return a list of Item nodes"""
        items = []
        for number, line in enumerate(base_lines, start=1):
            tax_ids = line['tax_ids']
            product_id = line['product_id']
            tax_details = line['tax_details']
            quantity = line['quantity']
            discount_percentage = line['discount']

            indicador_bieno_servicio = 0
            if product_id.type == 'service':
                indicador_bieno_servicio = '2'
            elif product_id.type == 'consu':
                indicador_bieno_servicio = '1'

            # Taxes with an invoicing indicator of either 1, 2, 3, 4 cannot be mixed and matched
            # For example, ITBIS 18% and ITBIS 16% cannot be set on the same invoice line
            # The expected singleton error is prevented functionally via _l10n_do_edi_check_invalid_tax_combo
            indicador_facturacion = tax_ids.filtered(lambda t: t.l10n_do_edi_invoicing_indicator in ITBIS_TAX_INDICATOR_VALUES).l10n_do_edi_invoicing_indicator if tax_ids else '0'

            # in company's currency
            price_unit = line['price_unit'] / line['rate']  # line['price_unit] is in invoice's currency
            discount_amount = price_unit * quantity * (discount_percentage / 100)  # Intentionally calculating discount_amount rather than using AccountTax discount methods
            line_subtotal = price_unit * quantity - discount_amount

            # in foreign currency
            otra_moneda_detalle_node = {}
            if line['currency_id'] != self.env.ref('base.DOP'):
                price_unit_currency = line['price_unit']
                discount_amount_currency = price_unit_currency * quantity * (discount_percentage / 100)
                line_subtotal_currency = price_unit_currency * quantity - discount_amount_currency
                otra_moneda_detalle_node.update({
                    'PrecioOtraMoneda': {'_text': f'{price_unit_currency:.4f}'},
                    'DescuentoOtraMoneda': {'_text': f'{discount_amount_currency:.2f}'} if discount_amount_currency else {},
                    'MontoItemOtraMoneda': {'_text': f'{line_subtotal_currency:.2f}'},
                })

            items.append({
                'NumeroLinea': {'_text': number},
                'IndicadorFacturacion': {'_text': indicador_facturacion},
                'Retencion': self._l10n_do_edi_get_retencion_node(tax_details['taxes_data']) if include_withholdings else {},
                'NombreItem': {'_text': product_id.name[:80]} if product_id.name else {},  # AlfNum80Type
                'IndicadorBienoServicio': {'_text': indicador_bieno_servicio} if indicador_bieno_servicio else {},
                'DescripcionItem': {'_text': line['name'][:100]} if line['name'] else {},  # AlfNum100Type
                'CantidadItem': {'_text': f'{quantity:.2f}'},
                'PrecioUnitarioItem': {'_text': f'{price_unit:.4f}'},  # Decimal20D1or4ValidationTypeMayorIgualCero
                'DescuentoMonto': {'_text': f'{discount_amount:.2f}'} if discount_amount else {},
                'TablaSubDescuento': {
                    'SubDescuento': {
                        'TipoSubDescuento': {'_text': '%'},
                        'SubDescuentoPorcentaje': {'_text': f'{discount_percentage:.2f}'},
                        'MontoSubDescuento': {'_text': f'{discount_amount:.2f}'},
                    },
                } if discount_percentage else {},
                'OtraMonedaDetalle': otra_moneda_detalle_node,
                'MontoItem': {'_text': f'{line_subtotal:.2f}'},  # Subtotal of line
            })
        return items

    def _l10n_do_edi_get_informacion_referencia_node(self):
        """Return the InformacionReferencia node"""
        ncf_modificado = {}
        fecha_ncf_modificado = {}
        if self.l10n_latam_document_type_id_code == '34':
            reversed_entry_id = self.reversed_entry_id
            ncf_modificado = {'_text': reversed_entry_id.name}
            fecha_ncf_modificado = {'_text': reversed_entry_id.invoice_date.strftime('%d-%m-%Y')}
        elif self.l10n_latam_document_type_id_code == '33':
            debit_origin_id = self.debit_origin_id
            ncf_modificado = {'_text': debit_origin_id.name}
            fecha_ncf_modificado = {'_text': debit_origin_id.invoice_date.strftime('%d-%m-%Y')}
        return {
                'NCFModificado': ncf_modificado,
                'FechaNCFModificado': fecha_ncf_modificado,
                'CodigoModificacion': {'_text': self.l10n_do_edi_modification_code},
                'RazonModificacion': {'_text': self.ref[:90]} if self.ref else {},  # AlfNum90ValidationType
        }

    def _l10n_do_edi_get_ecf_xml_content(self, company_id):
        """Generate the ecf xml content required"""
        self.ensure_one()
        # Gather the invoice lines with all its tax details to build Totales, OtraMoneda, Items
        base_lines, _tax_lines = self._get_rounded_base_and_tax_lines()
        self.env['account.tax']._add_tax_details_in_base_lines(base_lines, company_id)
        self.env['account.tax']._round_base_lines_tax_details(base_lines, company_id)

        id_doc_node = self._l10n_do_edi_get_id_doc_node()
        include_withholdings = self.l10n_latam_document_type_id_code != '32'
        content = {
            'Encabezado': {
                'Version': {'_text': '1.0'},
                'IdDoc': id_doc_node,
                'Emisor': {
                    'RNCEmisor': {'_text': company_id.vat},
                    'RazonSocialEmisor': {'_text': company_id.name[:150]},  # AlfNum150Type
                    'DireccionEmisor': {'_text': company_id.street[:100] if company_id.street else ''},  # AlfNum100Type
                    'FechaEmision': {'_text': fields.Date.context_today(self).strftime('%d-%m-%Y')},
                },
                'Comprador': self._l10n_do_edi_get_comprador_node(),
                'Totales': self._l10n_do_edi_get_totales_node(base_lines, include_withholdings),
                'OtraMoneda': self._l10n_do_edi_get_otra_moneda_node(base_lines),
            },
            'DetallesItems': {
                'Item': self._l10n_do_edi_get_items_node(base_lines, include_withholdings),
            },
            'InformacionReferencia': self._l10n_do_edi_get_informacion_referencia_node() if self.l10n_latam_document_type_id_code in ['33', '34'] else {},
        }
        return content

    def _l10n_do_edi_generate_ecf_xml(self, company_id):
        """Return the xml of the content and errors if any"""
        self.ensure_one()
        xml_content = self._l10n_do_edi_get_ecf_xml_content(company_id)
        try:
            xml = dict_to_xml(xml_content, template=ECF_TEMPLATES[self.l10n_latam_document_type_id_code])
        except ValueError as e:
            _logger.exception("ECF XML generation failed for %s", self.display_name)
            return '', str(e)
        return etree.tostring(xml, xml_declaration=True, encoding='UTF-8'), None
