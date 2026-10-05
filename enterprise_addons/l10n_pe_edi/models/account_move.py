# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import io
import re
import zipfile
from copy import deepcopy
from datetime import datetime
from hashlib import sha1
from zoneinfo import ZoneInfo

from lxml import etree, objectify
from num2words import num2words
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import HTTPError, InvalidSchema, InvalidURL, ReadTimeout, RequestException

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes, SQL, html2plaintext, html_escape
from odoo.tools.float_utils import float_round
from odoo.tools.zeep import Client, Settings

from odoo.addons.iap.tools.iap_tools import iap_jsonrpc
from odoo.addons.l10n_pe.tools.partner_identifiers import PE_RUC_SUNAT_CODE

DEFAULT_IAP_ENDPOINT = 'https://l10n-pe-edi.api.odoo.com'
DEFAULT_IAP_TEST_ENDPOINT = 'https://l10n-pe-edi.test.odoo.com'

CATALOG52 = [
    ("1002", "TRANSFERENCIA GRATUITA DE UN BIEN Y/O SERVICIO PRESTADO GRATUITAMENTE"),
    ("2000", "COMPROBANTE DE PERCEPCIÓN"),
    ("2001", "BIENES TRANSFERIDOS EN LA AMAZONÍA REGIÓN SELVAPARA SER CONSUMIDOS EN LA MISMA"),
    ("2002", "SERVICIOS PRESTADOS EN LA AMAZONÍA REGIÓN SELVA PARA SER CONSUMIDOS EN LA MISMA"),
    ("2003", "CONTRATOS DE CONSTRUCCIÓN EJECUTADOS EN LA AMAZONÍA REGIÓN SELVA"),
    ("2004", "Agencia de Viaje - Paquete turístico"),
    ("2005", "Venta realizada por emisor itinerante"),
    ("2006", "Operación sujeta a detracción"),
    ("2007", "Operación sujeta al IVAP"),
    ("2008", "VENTA EXONERADA DEL IGV-ISC-IPM. PROHIBIDA LA VENTA FUERA DE LA ZONA COMERCIAL DE TACNA"),
    ("2009", "PRIMERA VENTA DE MERCANCÍA IDENTIFICABLE ENTRE USUARIOS DE LA ZONA COMERCIAL"),
    ("2010", "Restitucion Simplificado de Derechos Arancelarios"),
    ("2011", "EXPORTACION DE SERVICIOS - DECRETO LEGISLATIVO Nº 919"),
]

REFUND_REASON = [
    ('01', 'Cancellation of the operation'),
    ('02', 'Cancellation by error in the RUC'),
    ('03', 'Correction by error in the description'),
    ('04', 'Global discount'),
    ('05', 'Discount per item'),
    ('06', 'Total refund'),
    ('07', 'Refund per item'),
    ('08', 'Bonus'),
    ('09', 'Decrease in value'),
    ('10', 'Other concepts'),
    ('11', 'Adjust in the exportation operation'),
    ('12', 'Adjust of IVAP'),
]

DEBIT_REASON = [
    ('01', 'Default interest'),
    ('02', 'Increase in value'),
    ('03', 'Other concepts'),
    ('11', 'Adjustments of export operations'),
    ('12', 'Adjustments affecting the IVAP'),
    ('13', 'Penalties'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_edi_is_required = fields.Boolean(
        string="Is the Peruvian EDI needed",
        compute='_compute_l10n_pe_edi_is_required')
    l10n_pe_edi_cancel_cdr_number = fields.Char(
        copy=False,
        help="Reference from webservice to consult afterwards.")
    l10n_pe_edi_refund_reason = fields.Selection(
        selection=REFUND_REASON,
        string="Credit Reason",
        help='It contains all possible values for the refund reason according to Catalog No. 09')
    l10n_pe_edi_charge_reason = fields.Selection(
        selection=DEBIT_REASON,
        string="Debit Reason",
        help='It contains all possible values for the charge reason according to Catalog No. 10')
    l10n_pe_edi_cancel_reason = fields.Char(
        string="Cancel Reason",
        copy=False,
        help="Peru: Reason given by the user for cancelling this move, structure of voided summary: sac:VoidReasonDescription.")
    l10n_pe_edi_operation_type = fields.Selection(
        selection=[
            ('0101', '[0101] Internal sale'),
            ('0112', '[0112] Internal Sale - Sustains Natural Person Deductible Expenses'),
            ('0113', '[0113] Internal Sale-NRUS'),
            ('0200', '[0200] Export of Goods'),
            ('0201', '[0201] Exportation of Services - Provision of services performed entirely in the country'),
            ('0202', '[0202] Exportation of Services - Provision of non-domiciled lodging services'),
            ('0203', '[0203] Exports of Services - Transport of shipping companies'),
            ('0204', '[0204] Exportation of Services - Services to foreign-flagged ships and aircraft'),
            ('0205', '[0205] Exportation of Services - Services that make up a Tourist Package'),
            ('0206', '[0206] Exports of Services - Complementary services to freight transport'),
            ('0207', '[0207] Exportation of Services - Supply of electric power in favor of subjects domiciled in ZED'),
            ('0208', '[0208] Exportation of Services - Provision of services partially carried out abroad'),
            ('0301', '[0301] Operations with air waybill (issued in the national scope)'),
            ('0302', '[0302] Passenger rail transport operations'), ('0303', '[0303] Oil royalty Pay Operations'),
            ('0401', '[0401] Non-domiciled sales that do not qualify as an export'),
            ('1001', '[1001] Operation Subject to Detraction'),
            ('1002', '[1002] Operation Subject to Detraction - Hydrobiological Resources'),
            ('1003', '[1003] Operation Subject to Drawdown - Passenger Transport Services'),
            ('1004', '[1004] Operation Subject to Drawdown - Cargo Transportation Services'),
            ('2001', '[2001] Operation Subject to Perception')
        ],
        string="Operation Type (PE)",
        store=True, readonly=False,
        compute='_compute_l10n_pe_edi_operation_type',
        init_storage=lambda self: self.env.cr.execute("""
                UPDATE account_move
                SET l10n_pe_edi_operation_type = '0101'
                FROM res_company
                JOIN res_country ON res_country.id = res_company.account_fiscal_country_id
                WHERE res_company.id = account_move.company_id
                   AND move_type IN ('out_invoice', 'out_refund')
                   AND res_country.code = 'PE'
                   AND l10n_pe_edi_operation_type IS NULL
            """),
        help="Peru: Defines the operation type, all the options can be used for all the document types, except "
             "'[0113] Internal Sale-NRUS' that is for document type 'Boleta' and '[0112] Internal Sale - Sustains "
             "Natural Person Deductible Expenses' exclusive for document type 'Factura'"
             "It can't be changed after validation. This is an optional feature added to avoid a warning. Catalog No. 51.")
    l10n_pe_edi_legend = fields.Selection(
        selection=CATALOG52,
        string="Legend Code", help="Peru: Specific operation type code.")
    l10n_pe_edi_legend_value = fields.Char(
        string="Legend",
        store=True, readonly=False, compute='_compute_l10n_pe_edi_legend_value',
        init_storage=lambda model: None,
        help="Peru: Specific operation type value.")

    l10n_pe_edi_status = fields.Selection(
        [
            ("to_send", "To Send"),
            ("sent", "Sent"),
            ("cancelled", "Cancelled"),
        ],
        string="Peru E-Invoice Status",
        store=True, copy=False,
        compute="_compute_l10n_pe_edi_status",
        help="Peru: the state of the most recent e-invoicing attempt.",
    )
    l10n_pe_edi_warnings = fields.Json(readonly=True, copy=False)
    l10n_pe_edi_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="E-Invoice(PE) Attachment",
        compute=lambda self: self._compute_linked_attachment_id('l10n_pe_edi_attachment_id', 'l10n_pe_edi_attachment_file'),
        depends=['l10n_pe_edi_attachment_file'],
    )
    l10n_pe_edi_attachment_file = fields.Binary(
        string="E-Invoice(PE) File",
        attachment=True,
        copy=False,
    )
    l10n_pe_edi_content = fields.Binary(
        compute="_compute_l10n_pe_edi_content",
        string="E-Invoice(PE) Content",
    )

    @api.constrains('name', 'company_id', 'move_type')
    def _prevent_invoices_with_same_edi_filename(self):
        for invoice in self.filtered(
            lambda m: (
                m.is_sale_document(include_receipts=True)
                and m.country_code == 'PE'
                and m.name not in (False, '/')
            )
        ):
            if self.search_count(
                [
                    ('country_code', '=', 'PE'),
                    ('move_type', 'in', ['out_invoice', 'out_refund', 'out_receipt']),
                    ('name', '=', invoice.name),
                    ('company_id.vat', '=', invoice.company_id.vat),
                    ('id', '!=', invoice.id),
                ],
                limit=1,
            ):
                raise ValidationError(self.env._('An invoice with the same sequence already exists. Please give this invoice a different sequence.'))

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('move_type', 'company_id')
    def _compute_l10n_pe_edi_is_required(self):
        for move in self:
            move.l10n_pe_edi_is_required = move.country_code == 'PE' \
                and move.is_sale_document() and move.l10n_latam_use_documents

    @api.depends('state', 'l10n_pe_edi_is_required')
    def _compute_l10n_pe_edi_status(self):
        for record in self:
            if record.state == 'posted' and record.l10n_pe_edi_is_required:
                record.l10n_pe_edi_status = 'to_send'

    @api.depends('move_type', 'company_id')
    def _compute_l10n_pe_edi_operation_type(self):
        for move in self:
            move.l10n_pe_edi_operation_type = '0101' if move.country_code == 'PE' and move.is_sale_document() else False

    @api.depends('l10n_pe_edi_legend')
    def _compute_l10n_pe_edi_legend_value(self):
        for move in self:
            if move.l10n_pe_edi_legend:
                matched_elements = [element for element in CATALOG52 if element[0] == move.l10n_pe_edi_legend]
                move.l10n_pe_edi_legend_value = matched_elements[0][1]
            else:
                move.l10n_pe_edi_legend_value = False

    @api.depends('journal_id', 'partner_id', 'company_id', 'move_type', 'debit_origin_id', 'l10n_pe_edi_operation_type')
    def _compute_l10n_latam_available_document_types(self):
        # EXTENDS 'l10n_latam_invoice_document'
        pe02_moves = self.filtered(
            lambda move: (
                move.state == 'draft'
                and move.country_code == 'PE'
                and move.partner_id.l10n_pe_sunat_id_code != PE_RUC_SUNAT_CODE
                and move.l10n_pe_edi_operation_type in ('0200', '0201', '0202', '0203', '0204', '0205', '0206', '0207', '0208')
                and move.journal_id.type == 'sale'
            )
        )
        for rec in pe02_moves.filtered(lambda move: move.move_type == 'out_invoice'):
            rec.l10n_latam_available_document_type_ids = self.env.ref('l10n_pe.document_type01') | self.env.ref('l10n_pe.document_type08')
        for rec in pe02_moves.filtered(lambda move: move.move_type == 'out_refund'):
            rec.l10n_latam_available_document_type_ids = self.env.ref('l10n_pe.document_type02')
        return super(AccountMove, self - pe02_moves)._compute_l10n_latam_available_document_types()

    @api.depends('l10n_pe_edi_is_required')
    def _compute_l10n_pe_edi_content(self):
        for move in self:
            if move.l10n_pe_edi_is_required and move.state != 'draft':
                xml_bstr, _errors = move._l10n_pe_edi_generate_invoice_bstr()
                move.l10n_pe_edi_content = BinaryBytes(xml_bstr) if xml_bstr else False
            else:
                move.l10n_pe_edi_content = False

    # -------------------------------------------------------------------------
    # SEQUENCE HACK
    # -------------------------------------------------------------------------

    def _get_last_sequence_domain(self, relaxed=False):
        # OVERRIDE
        condition = super()._get_last_sequence_domain(relaxed)
        if self.l10n_pe_edi_is_required:
            condition = SQL("%s AND l10n_latam_document_type_id = %s", condition, self.l10n_latam_document_type_id.id or 0)
        return condition

    def _get_starting_sequence(self):
        # OVERRIDE
        if self.l10n_pe_edi_is_required and self.l10n_latam_document_type_id:
            doc_mapping = {'01': 'FFI', '03': 'BOL', '07': 'CNE', '08': 'NDI'}
            middle_code = doc_mapping.get(self.l10n_latam_document_type_id_code, self.journal_id.code)
            # TODO: maybe there is a better method for finding decent 2nd journal default invoice names
            if self.journal_id.code != 'INV':
                middle_code = middle_code[:1] + self.journal_id.code[:2]
            return "%s %s-00000000" % (self.l10n_latam_document_type_id.doc_code_prefix, middle_code)

        return super()._get_starting_sequence()

    # -------------------------------------------------------------------------
    # EDI
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_get_serie_folio(self):
        number_match = list(re.finditer(r'\d+', self.name.replace(' ', '')))
        serie = self.name[:number_match[-1].start()].replace('-', '').replace(' ', '') or None
        folio = number_match[-1].group() or None
        return {'serie': serie, 'folio': folio}

    def _l10n_pe_edi_get_spot(self):
        self.ensure_one()
        max_percent = max(self.invoice_line_ids.mapped('product_id.l10n_pe_withhold_percentage'), default=0)
        if not max_percent or not self.l10n_pe_edi_operation_type in ['1001', '1002', '1003', '1004'] or self.move_type == 'out_refund':
            return {}
        line = self.invoice_line_ids.filtered(lambda r: r.product_id.l10n_pe_withhold_percentage == max_percent)[0]
        national_bank_account = self.company_id.bank_ids.filtered(lambda b: b._is_peruvian_national_bank_account())
        # just take the first one (but not meant to have multiple)
        national_bank_account_number = national_bank_account[0].account_number if national_bank_account else False
        has_installments = len(self.line_ids.filtered(lambda l: l.display_type == 'payment_term')) > 1

        # SUNAT requires the detraction amount to always be in PEN.
        # amount_total_signed is in the company currency, which is normally PEN.
        # When the company currency is not PEN, we must convert to PEN explicitly.
        pen_currency = self.env.ref('base.PEN')
        amount_in_pen = self.currency_id._convert(
            self.amount_total, pen_currency, self.company_id, self.invoice_date or fields.Date.today()
        )

        return {
            'id': 'Detraccion',
            'currency': pen_currency,
            'payment_means_id': line.product_id.l10n_pe_withhold_code,
            'payee_financial_account': national_bank_account_number,
            'payment_means_code': '999',
            'spot_amount': float_round(self.amount_total * (max_percent / 100.0), precision_rounding=1 if self.currency_id == pen_currency else self.currency_id.rounding),
            'amount': float_round(amount_in_pen * (max_percent / 100.0), precision_rounding=1),
            'payment_percent': max_percent,
            'has_installments': has_installments,
        }

    def _l10n_pe_edi_post_invoice(self):
        self.ensure_one()
        self.l10n_pe_edi_warnings = {}
        edi_str, errors = self._l10n_pe_edi_generate_invoice_bstr()
        res = {}

        if errors:
            res = {
                'message': self.env._("Errors occurred while creating the EDI document:") + "\n" + "\n".join(errors),
                'level': 'danger',
            }
        elif edi_str:
            self.lock_for_update()
            if self.company_id.l10n_pe_edi_provider == 'iap':
                res = self._l10n_pe_edi_sign_invoices_iap(edi_str)
            else:
                res = self._l10n_pe_edi_sign_invoices_sunat_estela(edi_str)

        # CDR error codes 1033 and 4000 mean that the invoice was already registered with the OSE.
        # In this case, we want to retrieve the CDR, except if there was already an invoice with the
        # same edi_filename that was sent. In that case, we want the duplicate error to bubble up, so
        # the user knows they must resequence.
        if res.get('message') and res.get('code') in ['1033', '4000']:
            if self.env['account.move'].search_count([
                ('company_id.vat', '=', self.company_id.vat),
                ('l10n_latam_document_type_id.code', '=', self.l10n_latam_document_type_id_code),
                ('name', '=', self.name),
                ('l10n_pe_edi_status', '=', 'sent'),
                ('id', '!=', self.id),
            ]):
                res['message'] += '<br/>' + self.env._("Please resequence the invoice to a number not yet sent to SUNAT.")
            else:
                res_retrieve_cdr = self._l10n_pe_edi_retrieve_cdr()
                if res_retrieve_cdr.get('message'):
                    res['message'] = f"{res['message']}<br/>{res_retrieve_cdr['message']}"
                    # SUNAT already accepted the document (that's why we got 1033/4000), so if we
                    # still can't retrieve the CDR at this point, propagate whether that's worth an
                    # automatic retry (CDR simply isn't generated yet) or a lost cause.
                    res['retry'] = res_retrieve_cdr.get('retry', False)
                else:
                    # Check that the partner and issue date match between the retrieved CDR and the invoice.
                    cdr = res_retrieve_cdr['cdr']
                    cdr_tree = etree.fromstring(cdr)
                    retrieved_cdr_document_id = cdr_tree.find('.//{*}DocumentReference//{*}ID')
                    is_same_document_id = retrieved_cdr_document_id.text == self.name.replace(' ', '') if retrieved_cdr_document_id is not None else True
                    retrieved_cdr_ruc = cdr_tree.find('.//{*}RecipientParty//{*}CompanyID')
                    is_same_ruc = retrieved_cdr_ruc.text == self.partner_id.vat if retrieved_cdr_ruc is not None else True
                    if is_same_document_id and is_same_ruc:
                        # If the CDR already exists and is valid on SUNAT's side, then likely the invoice was already sent once, but
                        # Odoo hit an exception and rolled back the transaction after sending.
                        # In this case, we want to retrieve the CDR and continue as if sending succeeded.
                        self.message_post(body=self.env._('The invoice already exists on SUNAT. CDR successfully retrieved.'))
                        res = {'success': True, 'xml_document': res['xml_document'], 'cdr': cdr}

        if res.get('message'):
            self.l10n_pe_edi_warnings = self._l10n_pe_edi_transform_error(res)
            # Account Move Send will raise a UserError for any errors found during EDI posting.
            # To guarantee that the error messages persist on the move we need to commit.
            if self._can_commit():
                self.env.cr.commit()
            return res

        # Chatter.
        documents = []
        edi_filename = self._l10n_pe_edi_generate_edi_filename()
        if res.get('xml_document'):
            documents.append(('%s.xml' % edi_filename, res['xml_document']))
        if res.get('cdr'):
            documents.append(('CDR-%s.xml' % edi_filename, res['cdr']))
        if documents:
            zip_edi_str = self._l10n_pe_edi_zip_edi_document(documents)
            attachment_id = self.env['ir.attachment'].create({
                'res_model': self._name,
                'res_id': self.id,
                'res_field': 'l10n_pe_edi_attachment_file',
                'type': 'binary',
                'name': '%s.zip' % edi_filename,
                'raw': zip_edi_str,
                'mimetype': 'application/zip',
            })

            if self.company_id.l10n_pe_edi_test_env:
                message = self.env._("Testing environment is active, care that those documents are not synced with SUNAT!")
            else:
                message = self.env._("The EDI document was successfully created and signed by the government.")
            self.message_post(
                body=message,
                attachment_ids=attachment_id.ids,
            )
            self.l10n_pe_edi_status = 'sent'
        return None

    def _l10n_pe_edi_retrieve_cdr(self):
        if self.company_id.l10n_pe_edi_provider == 'iap':
            res_status_cdr = self._l10n_pe_edi_get_status_cdr_iap()
        else:
            res_status_cdr = self._l10n_pe_edi_get_status_cdr_sunat_estela()

        if res_status_cdr.get('message'):
            error_msg = '%s<br/>%s' % (self.env._('Error when requesting CDR status:'), res_status_cdr['message'])
            # Propagate the service's own verdict: 'retry' True means we don't have a definitive answer
            # yet (connection issue, or the CDR simply isn't generated yet) and is worth retrying
            # automatically, anything else (like a SOAP fault from SUNAT) is not retried.
            return {'message': error_msg, 'retry': res_status_cdr.get('retry', False)}
        if res_status_cdr.get('code') != '0004':
            error_msg = '%s<br/>%s' % (self.env._('SOAP response status when retrieving CDR:'), res_status_cdr['status'])
            # Same as above: still no definitive answer, keep retrying.
            return {'message': error_msg, 'retry': True}
        # SOAP status code is 0004: CDR already exists.
        # Decode the CDR. If the CDR's ResponseCode is 0, then it is valid; otherwise SUNAT considers it invalid.
        cdr = res_status_cdr['cdr']
        cdr_status = self._l10n_pe_edi_extract_cdr_status(cdr)
        if cdr_status['code'] != '0':
            error_message = '%s<br/>%s<br/><br/><b>%s</b>' % (
                self.env._('Retrieved CDR status:'),
                cdr_status['description'],
                self.env._('This document number is now registered by SUNAT as invalid.'),
            )
            # SUNAT has definitively rejected the document: retrying won't produce a different
            # answer, so this must not be retried by the send cron forever.
            return {'message': error_message}
        return res_status_cdr

    def _l10n_pe_edi_cancel_invoice(self):
        self.ensure_one()
        self.lock_for_update()
        # Perform the actual EDI cancellation
        api_error = self._l10n_pe_edi_do_cancel_invoice()
        if api_error:
            self.l10n_pe_edi_warnings = self._l10n_pe_edi_transform_error(api_error)
        else:
            self.button_draft()
            self.button_cancel()
            self.l10n_pe_edi_status = 'cancelled'

    def _l10n_pe_edi_do_cancel_invoice(self):
        res = {}
        self.l10n_pe_edi_warnings = {}
        if not self.l10n_pe_edi_cancel_cdr_number:
            # Cancellation step 1. Mark the invoice for cancellation.
            certificate_date = datetime.now(tz=ZoneInfo('America/Lima')).date()
            reference_date = self.invoice_date
            company = self.company_id

            # Prepare the void documents to void all invoices at once.
            void_number = self.env['ir.sequence'].next_by_code('l10n_pe_edi.summary.sequence')
            void_values = {
                'certificate_date': certificate_date,
                'reference_date': reference_date,
                'void_number': void_number,
                'company': company,
                'records': self,
            }
            void_str = self.env['ir.qweb']._render('l10n_pe_edi.ubl_pe_21_voided_documents', void_values).encode()
            void_filename = '%s-%s' % (company.vat, void_number)

            if self.company_id.l10n_pe_edi_provider == 'iap':
                res = self._l10n_pe_edi_cancel_invoice_step_1_iap(void_filename, void_str)
            else:
                res = self._l10n_pe_edi_cancel_invoice_step_1_sunat_estela(void_filename, void_str)

            if res.get('message'):
                return res

            if not res.get('cdr_number'):
                error = self.env._("The EDI document failed to be cancelled because the cancellation CDR number is missing.")
                return {'message': error}
            # Chatter.
            message = self.env._("Cancellation is in progress in the government side (CDR number: %s).", html_escape(res['cdr_number']))
            if res.get('xml_document'):
                void_attachment = self.env['ir.attachment'].create({
                    'type': 'binary',
                    'name': 'VOID-%s.xml' % void_filename,
                    'raw': res['xml_document'],
                    'mimetype': 'application/xml',
                })
                self.message_post(
                    body=message,
                    attachment_ids=void_attachment.ids,
                )

            self.l10n_pe_edi_cancel_cdr_number = res['cdr_number']

        # Cancellation Step 2. Check if it was successfully cancel it.

        if self.company_id.l10n_pe_edi_provider == 'iap':
            res = self._l10n_pe_edi_cancel_invoice_step_2_iap()
        else:
            res = self._l10n_pe_edi_cancel_invoice_step_2_sunat_estela()

        if res.get('message'):
            return res
        if not res.get('success'):
            error = self.env._("The EDI document failed to be cancelled for unknown reason.")
            return {'message': error}

        # Chatter.
        message = self.env._("The EDI document was successfully cancelled by the government (CDR number: %s).", html_escape(self.l10n_pe_edi_cancel_cdr_number))
        cdr_void_attachment = self.env['ir.attachment'].create({
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'name': 'CDR-VOID-%s.xml' % self._l10n_pe_edi_generate_edi_filename(),
            'raw': res['cdr'],
            'mimetype': 'application/xml',
        })

        self.message_post(
            body=message,
            attachment_ids=cdr_void_attachment.ids,
        )
        self.l10n_pe_edi_attachment_id.res_field = False
        self.l10n_pe_edi_cancel_cdr_number = False
        return None
    # -------------------------------------------------------------------------
    # EDI: IAP services
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_pe_edi_get_iap_buy_credits_message(self):
        url = self.env['iap.account'].get_credits_url(service_name="l10n_pe_edi")
        return {
            "message": self.env._("You have insufficient credits to sign or verify this document!\nPlease proceed to buy more credits."),
            "level": 'danger',
            "action_text": self.env._("Buy Credits"),
            "action": {'type': 'ir.actions.act_url', 'url': url},
        }

    @api.model
    def _l10n_pe_edi_get_iap_params(self, company):
        ir_params = self.env['ir.config_parameter'].sudo()
        if company.l10n_pe_edi_test_env:
            default_endpoint = DEFAULT_IAP_TEST_ENDPOINT
        else:
            default_endpoint = DEFAULT_IAP_ENDPOINT
        iap_server_url = ir_params.get_str('l10n_pe_edi.endpoint') or default_endpoint
        iap_token = self.env['iap.account'].get('l10n_pe_edi').sudo().account_token
        dbuuid = ir_params.get_str('database.uuid')
        return dbuuid, iap_server_url, iap_token

    def _l10n_pe_edi_sign_invoices_iap(self, edi_str):
        self.ensure_one()

        edi_tree = objectify.fromstring(edi_str)

        # Dummy Signature to allow check the XSD, this will be replaced on IAP.
        namespaces = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
        edi_tree_copy = deepcopy(edi_tree)
        signature_element = edi_tree_copy.xpath('.//ds:Signature', namespaces=namespaces)[0]
        signature_str = self.env['ir.qweb']._render('l10n_pe_edi.ubl_pe_21_signature_template', {'digest_value': ''})
        signature_element.getparent().replace(signature_element, objectify.fromstring(signature_str))

        dbuuid, iap_server_url, iap_token = self._l10n_pe_edi_get_iap_params(self.company_id)

        rpc_params = {
            'vat': self.company_id.vat,
            'doc_type': self.l10n_latam_document_type_id_code,
            'dbuuid': dbuuid,
            'fname': self._l10n_pe_edi_generate_edi_filename(),
            'xml': BinaryBytes(edi_str).to_base64(),
            'token': iap_token,
        }

        try:
            result = iap_jsonrpc(iap_server_url + '/iap/l10n_pe_edi/1/send_bill', params=rpc_params, timeout=60)
        except (InvalidSchema, InvalidURL):
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE18'], 'level': 'danger'}
        except RequestException:
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE17'], 'level': 'warning'}

        if result.get('message'):
            if result['message'] == 'no-credit':
                return self._l10n_pe_edi_get_iap_buy_credits_message()
            return {'message': result['message'], 'level': 'danger'}

        xml_document = result.get('signed') and self._l10n_pe_edi_unzip_edi_document(base64.b64decode(result['signed']))

        soap_response = result.get('cdr') and base64.b64decode(result['cdr'])
        soap_response_decoded = self._l10n_pe_edi_decode_soap_response(soap_response) if soap_response else {}

        if soap_response_decoded.get('error'):
            return {'message': soap_response_decoded['error'], 'level': 'danger',
                    'code': soap_response_decoded.get('code'), 'xml_document': xml_document}

        cdr = soap_response_decoded['cdr']
        cdr_status = self._l10n_pe_edi_extract_cdr_status(cdr)

        if cdr_status['code'] != '0':
            error_message = '%s<br/><br/><b>%s</b>' % (
                cdr_status['description'],
                self.env._('This document number is now registered by SUNAT as invalid.'),
            )
            return {'message': error_message, 'level': 'danger',
                    'code': cdr_status['code'], 'xml_document': xml_document}

        return {'success': True, 'xml_document': xml_document, 'cdr': cdr}

    def _l10n_pe_edi_get_status_cdr_iap(self):
        dbuuid, iap_server_url, iap_token = self._l10n_pe_edi_get_iap_params(self.company_id)
        serie_folio = self._l10n_pe_edi_get_serie_folio()

        rpc_params = {
            'vat': self.company_id.vat,
            'doc_type': self.l10n_latam_document_type_id_code,
            'dbuuid': dbuuid,
            'serie': serie_folio['serie'],
            'folio': serie_folio['folio'],
            'token': iap_token,
        }

        try:
            result = iap_jsonrpc(iap_server_url + '/iap/l10n_pe_edi/1/get_status_cdr', params=rpc_params, timeout=1500)
        except (InvalidSchema, InvalidURL):
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE18'], 'level': 'danger'}
        except RequestException:
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE17'], 'level': 'warning', 'retry': True}

        if result.get('message'):
            if result['message'] == 'no-credit':
                return self._l10n_pe_edi_get_iap_buy_credits_message()
            return {'message': result['message'], 'level': 'danger'}

        soap_response = result.get('cdr') and base64.b64decode(result['cdr'])
        soap_response_decoded = self._l10n_pe_edi_decode_soap_response(soap_response) if soap_response else {}

        if soap_response_decoded.get('error'):
            return {
                'message': soap_response_decoded['error'],
                'level': 'danger',
                'code': soap_response_decoded.get('code'),
                'retry': soap_response_decoded.get('retry', False),
            }

        code = soap_response_decoded.get('code')
        status = '%s|%s' % (html_escape(code), html_escape(soap_response_decoded.get('message')))
        cdr = soap_response_decoded.get('cdr')

        return {'cdr': cdr, 'status': status, 'code': code}

    def _l10n_pe_edi_cancel_invoice_step_1_iap(self, void_filename, void_str):
        self.ensure_one()
        dbuuid, iap_server_url, iap_token = self._l10n_pe_edi_get_iap_params(self.company_id)

        rpc_params = {
            'vat': self.company_id.vat,
            'dbuuid': dbuuid,
            'fname': void_filename,
            'xml': base64.encodebytes(void_str).decode('utf-8'),
            'token': iap_token,
        }

        try:
            result = iap_jsonrpc(iap_server_url + '/iap/l10n_pe_edi/1/send_summary', params=rpc_params, timeout=15)
        except (InvalidSchema, InvalidURL):
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE18'], 'level': 'danger'}
        except RequestException:
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE17'], 'level': 'warning'}

        if result.get('message'):
            if result['message'] == 'no-credit':
                return self._l10n_pe_edi_get_iap_buy_credits_message()
            return {'message': result['message'], 'level': 'danger'}

        soap_response = result.get('cdr') and base64.b64decode(result['cdr'])
        soap_response_decoded = self._l10n_pe_edi_decode_soap_response(soap_response) if soap_response else {}

        if soap_response_decoded.get('error'):
            return {'message': soap_response_decoded['error'], 'level': 'danger', 'code': soap_response_decoded.get('code')}

        cdr_number = soap_response_decoded['number']
        xml_document = result.get('signed') and self._l10n_pe_edi_unzip_edi_document(base64.b64decode(result['signed']))
        return {'xml_document': xml_document, 'cdr': soap_response, 'cdr_number': cdr_number}

    def _l10n_pe_edi_cancel_invoice_step_2_iap(self):
        self.ensure_one()
        dbuuid, iap_server_url, iap_token = self._l10n_pe_edi_get_iap_params(self.company_id)

        rpc_params = {
            'vat': self.company_id.vat,
            'dbuuid': dbuuid,
            'number': self.l10n_pe_edi_cancel_cdr_number,
            'token': iap_token,
        }

        try:
            result = iap_jsonrpc(iap_server_url + '/iap/l10n_pe_edi/1/get_status', params=rpc_params, timeout=15)
        except (InvalidSchema, InvalidURL):
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE18'], 'level': 'danger'}
        except RequestException:
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE17'], 'level': 'warning'}

        if result.get('message'):
            if result['message'] == 'no-credit':
                return self._l10n_pe_edi_get_iap_buy_credits_message()
            return {'message': result['message'], 'level': 'danger'}

        return self._l10n_pe_edi_parse_cancel_soap(result.get('cdr') and base64.b64decode(result['cdr']))

    # -------------------------------------------------------------------------
    # EDI: SUNAT / Estela (formerly DIGIFLOW) services
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_pe_edi_send_bill_sunat_estela(self, credentials, filename, zip_edi_str):
        """Send a zipped EDI document via SOAP sendBill and return the decoded SOAP response."""
        try:
            settings = Settings(raw_response=True)
            client = Client(
                wsdl=credentials['wsdl'],
                wsse=credentials['token'],
                settings=settings,
                operation_timeout=15,
                timeout=15,
            )
            result = client.service.sendBill('%s.zip' % filename, zip_edi_str)
            # SUNAT will return a 500 Server Error (!) with a SOAP response if the invoice already exists.
            # In that case, we still want to try to decode the response.
            if result.status_code != 500:
                result.raise_for_status()
        except (ReqConnectionError, HTTPError, TypeError, ReadTimeout):
            return {'error': self._l10n_pe_edi_get_general_error_messages()['L10NPE08'], 'level': 'warning'}
        soap_response = result.content
        return self._l10n_pe_edi_decode_soap_response(soap_response) if soap_response else {}

    def _l10n_pe_edi_sign_invoices_sunat_estela(self, edi_str):
        credentials = self.company_id._l10n_pe_edi_get_credentials(
            sunat_wsdl=self._l10n_pe_edi_get_sunat_invoice_wsdl(),
        )

        if not self.company_id.sudo().l10n_pe_edi_certificate_id:
            return {'message': self.env._("No valid certificate found for %s company.", self.company_id.display_name)}

        # Sign the document.
        edi_tree = objectify.fromstring(edi_str)
        edi_tree = self._l10n_pe_edi_sign(self.company_id.sudo().l10n_pe_edi_certificate_id, edi_tree)
        edi_str = etree.tostring(edi_tree, xml_declaration=True, encoding='ISO-8859-1')

        filename = self._l10n_pe_edi_generate_edi_filename()
        zip_edi_str = self._l10n_pe_edi_zip_edi_document([('%s.xml' % filename, edi_str)])
        soap_response_decoded = self._l10n_pe_edi_send_bill_sunat_estela(credentials, filename, zip_edi_str)

        if soap_response_decoded.get('error'):
            return {'message': soap_response_decoded['error'], 'level': soap_response_decoded.get('level', 'danger'),
                    'code': soap_response_decoded.get('code'), 'xml_document': edi_str}

        cdr = soap_response_decoded['cdr']
        cdr_status = self._l10n_pe_edi_extract_cdr_status(cdr)

        if cdr_status['code'] != '0':
            error_message = '%s<br/><br/><b>%s</b>' % (
                cdr_status['description'],
                self.env._('This document number is now registered by SUNAT as invalid.'),
            )
            return {'message': error_message, 'level': 'danger',
                    'code': cdr_status['code'], 'xml_document': edi_str}

        return {'success': True, 'xml_document': edi_str, 'cdr': cdr}

    def _l10n_pe_edi_get_status_cdr_sunat_estela(self):
        credentials = self.company_id._l10n_pe_edi_get_credentials(
            sunat_wsdl=self._l10n_pe_edi_get_sunat_invoice_wsdl(cdr=True),
        )
        try:
            settings = Settings(raw_response=True)
            client = Client(
                wsdl=credentials['wsdl'],
                wsse=credentials['token'],
                settings=settings,
                operation_timeout=15,
                timeout=15,
            )
            serie_folio = self._l10n_pe_edi_get_serie_folio()
            result = client.service.getStatusCdr(self.company_id.vat, self.l10n_latam_document_type_id_code, serie_folio['serie'], serie_folio['folio'])
            result.raise_for_status()
        except (ReqConnectionError, HTTPError, TypeError, ReadTimeout):
            return {'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE08'], 'level': 'warning', 'retry': True}
        soap_response = result.content
        soap_response_decoded = self._l10n_pe_edi_decode_soap_response(soap_response) if soap_response else {}

        if soap_response_decoded.get('error'):
            return {
                'message': soap_response_decoded['error'],
                'level': 'danger',
                'code': soap_response_decoded.get('code'),
                'retry': soap_response_decoded.get('retry', False),
            }

        code = soap_response_decoded.get('code')
        status = '%s|%s' % (html_escape(code), html_escape(soap_response_decoded.get('message')))
        cdr = soap_response_decoded.get('cdr')

        return {'cdr': cdr, 'status': status, 'code': code}

    def _l10n_pe_edi_cancel_invoice_step_1_sunat_estela(self, void_filename, void_str):
        self.ensure_one()

        credentials = self.company_id._l10n_pe_edi_get_credentials(
            sunat_wsdl=self._l10n_pe_edi_get_sunat_invoice_wsdl(),
        )

        void_tree = objectify.fromstring(void_str)
        void_tree = self._l10n_pe_edi_sign(self.company_id.sudo().l10n_pe_edi_certificate_id, void_tree)
        void_str = etree.tostring(void_tree, xml_declaration=True, encoding='ISO-8859-1')
        zip_void_str = self._l10n_pe_edi_zip_edi_document([('%s.xml' % void_filename, void_str)])

        try:
            settings = Settings(raw_response=True)
            client = Client(
                wsdl=credentials['wsdl'],
                wsse=credentials['token'],
                settings=settings,
                operation_timeout=15,
                timeout=15,
            )
            result = client.service.sendSummary('%s.zip' % void_filename, zip_void_str)
            result.raise_for_status()
        except (ReqConnectionError, HTTPError, TypeError, ReadTimeout):
            return {
                'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE08'],
                'level': 'warning',
                'action_call': ('account.move', 'button_request_cancel', self.ids),
                'action_text': self.env._("Retry cancellation"),
            }
        soap_response = result.content
        soap_response_decoded = self._l10n_pe_edi_decode_soap_response(soap_response)

        if soap_response_decoded.get('error'):
            return {'message': soap_response_decoded['error'], 'level': 'danger', 'code': soap_response_decoded.get('code')}

        cdr_number = soap_response_decoded['number']
        return {'xml_document': void_str, 'cdr': soap_response, 'cdr_number': cdr_number}

    def _l10n_pe_edi_cancel_invoice_step_2_sunat_estela(self):
        self.ensure_one()

        credentials = self.company_id._l10n_pe_edi_get_credentials(
            sunat_wsdl=self._l10n_pe_edi_get_sunat_invoice_wsdl(),
        )

        try:
            settings = Settings(raw_response=True)
            client = Client(
                wsdl=credentials['wsdl'],
                wsse=credentials['token'],
                settings=settings,
                operation_timeout=15,
                timeout=15,
            )
            result = client.service.getStatus(self.l10n_pe_edi_cancel_cdr_number)
            result.raise_for_status()
        except (ReqConnectionError, HTTPError, TypeError, ReadTimeout):
            return {
                'message': self._l10n_pe_edi_get_general_error_messages()['L10NPE08'],
                'level': 'warning',
                'action_call': ('account.move', 'button_request_cancel', self.ids),
                'action_text': self.env._("Retry cancellation"),
            }
        return self._l10n_pe_edi_parse_cancel_soap(result.content)

    # -------------------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_amount_to_text(self):
        """Transform a float amount to text words on peruvian format: AMOUNT IN TEXT 11/100
        :returns: Amount transformed to words peruvian format for invoices
        :rtype: str
        """
        self.ensure_one()
        amount_i, amount_d = divmod(self.amount_total, 1)
        amount_d = int(round(amount_d * 100, 2))
        words = num2words(amount_i, lang='es')
        result = '%(words)s Y %(amount_d)02d/100 %(currency_name)s' % {
            'words': words,
            'amount_d': amount_d,
            'currency_name':  self.currency_id.currency_unit_label,
        }
        return result.upper()

    def _l10n_pe_edi_get_extra_report_values(self):
        ''' Get values from the current invoice in order to render extra informations in the report.

        Qr-code documentation:
        https://cpe.sunat.gob.pe/sites/default/files/inline-files/Aspectos%20t%C3%A9cnicos%20-%20emisor%20electr%C3%B3nico_0.pdf#page=6

        Example of the text:
        '20557912879|6|FPPP|2346274|603.61|3957.01|2020-07-15|6|20462509236|5zVcyL443M1vVGhdFNi+H9jcslo=|\r\n'

        That specifies the next fields to be in the QR and Pipe separated:
        a) RUC number of the invoice issuer
        b) Document type
        c) Number conformed by serie and correlative
        d) IGV in case of having it
        e) Total amount
        f) Emission date
        g) Document type of the partner
        h) Document number of the partner

        :return: A python dictionary.
        '''
        self.ensure_one()

        # Parse the edi document.
        edi_attachment_zipped = self.l10n_pe_edi_attachment_file
        if not edi_attachment_zipped:
            return {}
        edi_attachment_str = self._l10n_pe_edi_unzip_edi_document(edi_attachment_zipped.content)
        edi_tree = etree.fromstring(edi_attachment_str)

        # Qr-code
        signature_hash = edi_tree.xpath('//ds:DigestValue', namespaces={'ds': 'http://www.w3.org/2000/09/xmldsig#'})[0].text
        igv_tax_amount = ''
        nsmap = {k: v for k, v in edi_tree.nsmap.items() if k}
        for tax_element in edi_tree.xpath('//cac:TaxSubtotal', namespaces=nsmap):
            tax_name_elements = tax_element.xpath(".//cac:TaxScheme/cbc:Name", namespaces=nsmap)
            tax_amount_elements = tax_element.xpath(".//cbc:TaxAmount", namespaces=nsmap)
            if tax_name_elements and tax_amount_elements and tax_name_elements[0].text == 'IGV':
                igv_tax_amount = tax_amount_elements[0].text
                break

        serie_folio = self._l10n_pe_edi_get_serie_folio()
        partner_identification_type = self.partner_id.l10n_pe_sunat_id_code
        qr_code_values = [
            self.company_id.vat,
            self.company_id.partner_id.l10n_pe_sunat_id_code,
            serie_folio['serie'],
            serie_folio['folio'],
            igv_tax_amount,
            str(self.amount_total),
            fields.Date.to_string(self.date),
            partner_identification_type,
            self.commercial_partner_id.l10n_pe_sunat_id_value or '00000000',
            signature_hash,
        ]

        return {
            'qr_str': '|'.join(qr_code_values) + '|\r\n',
            'amount_to_text': self._l10n_pe_edi_amount_to_text(),
        }

    def _l10n_pe_edi_get_payment_means(self):
        payment_means_id = 'Credito'
        if not self.invoice_date_due or self.invoice_date_due == self.invoice_date:
            payment_means_id = 'Contado'
        return payment_means_id

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def button_request_cancel(self):
        # OVERRIDES 'account'
        if self.l10n_pe_edi_status == 'sent':
            if self.l10n_latam_document_type_id_code == '03':
                raise UserError(self.env._("Invoices with this document type always need to be cancelled through a credit note. "
                                  "There is no possibility to cancel."))
            if self.l10n_pe_edi_cancel_reason:
                return self._l10n_pe_edi_cancel_invoice()
            return self.env.ref('l10n_pe_edi.action_l10n_pe_edi_cancel').sudo().read()[0]
        return super().button_request_cancel()

    def _need_cancel_request(self):
        # EXTENDS 'account'
        return super()._need_cancel_request() or self.l10n_pe_edi_status == 'sent'

    def button_draft(self):
        # EXTENDS 'account'
        self.write(
            {
                "l10n_pe_edi_status": False,
                "l10n_pe_edi_warnings": False,
            },
        )
        return super().button_draft()

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.l10n_latam_use_documents and self.company_id.country_id.code == 'PE':
            return 'l10n_pe_edi.report_invoice_document'
        return super()._get_name_invoice_report()

    def _get_fields_to_detach(self):
        # EXTENDS account
        fields_list = super()._get_fields_to_detach()
        fields_list.append('l10n_pe_edi_attachment_file')
        return fields_list

    # -------------------------------------------------------------------------
    # EDI: HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_pe_edi_zip_edi_document(self, documents):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, content in documents:
                zf.writestr(filename, content)
        content = buffer.getvalue()
        buffer.close()
        return content

    @api.model
    def _l10n_pe_edi_unzip_edi_document(self, zip_bytes):
        """Unzip the first XML file of a zip file,
        or, if the zip file does not contain an XML file, unzip the first file.
        :param zip_bytes: zipfile bytes
        :returns: the contents of the first xml file (or first file)
        """
        buffer = io.BytesIO(zip_bytes)
        zipfile_obj = zipfile.ZipFile(buffer)
        # We need to select the first xml file of the zip file because SUNAT sometimes sends a CDR zip file
        # which has an empty folder named 'dummy' as the first file in the zip file.
        filenames = zipfile_obj.namelist()
        xml_filenames = [x for x in filenames if x.endswith(('.xml', '.XML'))]
        filename_to_decode = xml_filenames[0] if xml_filenames else filenames[0]
        content = zipfile_obj.read(filename_to_decode)
        buffer.close()
        return content

    @api.model
    def _l10n_pe_edi_extract_cdr_status(self, cdr):
        """
        Parse a CDR in XML format.

        Returns a dict that contains the following fields:
        'code': the ResponseCode of the CDR. 0 = success. Any other value = error.
        'description': a description of the CDR's response in HTML format, combining the
                       'Description' tag and the 'Note' tags.
        """
        cdr_tree = etree.fromstring(cdr)
        code = cdr_tree.find('.//{*}ResponseCode').text
        description = html_escape(cdr_tree.find('.//{*}Description').text)
        notes = cdr_tree.findall('.//{*}Note')
        for note in notes:
            description += '<br/>' + html_escape(note.text)

        if code != '0':
            error_messages_map = self._l10n_pe_edi_get_cdr_error_messages()
            description = '%s<br/><br/><b>%s</b><br/>%s|%s' % (
                error_messages_map.get(code, self.env._("We got an error response from the OSE. ")),
                self.env._('Original message:'),
                html_escape(code),
                html_escape(description),
            )

        return {'code': code, 'description': description}

    @api.model
    def _l10n_pe_edi_sign(self, certificate, edi_tree):
        namespaces = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}

        edi_tree_copy = deepcopy(edi_tree)
        signature_element = edi_tree_copy.xpath('.//ds:Signature', namespaces=namespaces)[0]
        signature_element.getparent().remove(signature_element)

        edi_tree_c14n_str = etree.tostring(edi_tree_copy, method='c14n', exclusive=True, with_comments=False)
        digest_b64 = base64.b64encode(sha1(edi_tree_c14n_str).digest())
        signature_str = self.env['ir.qweb']._render(
            'l10n_pe_edi.ubl_pe_21_signature_template',
            {'digest_value': digest_b64.decode()},
        )

        # Eliminate all non useful spaces and new lines in the stream
        signature_str = signature_str.replace('\n', '').replace('  ', '')

        signature_tree = etree.fromstring(signature_str)
        signed_info_element = signature_tree.xpath('.//ds:SignedInfo', namespaces=namespaces)[0]
        signature = etree.tostring(signed_info_element, method='c14n', exclusive=True, with_comments=False)
        signature_b64_hash = certificate._sign(signature, hashing_algorithm='sha1', formatting='base64')

        signature_tree.xpath('.//ds:SignatureValue', namespaces=namespaces)[0].text = signature_b64_hash
        signature_tree.xpath('.//ds:X509Certificate', namespaces=namespaces)[0].text = certificate._get_der_certificate_bytes(formatting='base64')
        signed_edi_tree = deepcopy(edi_tree)
        signature_element = signed_edi_tree.xpath('.//ds:Signature', namespaces=namespaces)[0]
        for child_element in signature_tree:
            signature_element.append(child_element)
        return signed_edi_tree

    def _l10n_pe_edi_generate_edi_filename(self):
        self.ensure_one()
        return '%s-%s-%s' % (
            self.company_id.vat,
            self.l10n_latam_document_type_id_code,
            self.name.replace(' ', ''),
        )

    def _l10n_pe_edi_generate_invoice_bstr(self):
        self.ensure_one()

        if not self.l10n_latam_document_type_id_code in {'07', '08', '01', '03'}:
            return None, [self.env._("Missing LATAM document code.")]

        builder = self.env['account.edi.xml.ubl_pe']
        xml_content, errors = builder._export_invoice(self)

        if errors:
            return None, errors

        # Since the default UBL construction removes empty nodes, we need to recreate them here.
        edi_tree = objectify.fromstring(xml_content)
        namespaces = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
        ubl_version_id_element = edi_tree.xpath('.//cbc:UBLVersionID', namespaces=namespaces)[0]
        ubl_extensions_str = self.env['ir.qweb']._render('l10n_pe_edi.ubl_pe_21_ubl_extensions_empty_signature')
        ubl_version_id_element.addprevious(objectify.fromstring(ubl_extensions_str))

        return etree.tostring(edi_tree), []

    def _l10n_pe_edi_get_sunat_invoice_wsdl(self, cdr=False):
        self.ensure_one()
        if cdr:
            return 'https://e-factura.sunat.gob.pe/ol-it-wsconscpegem/billConsultService?wsdl'
        if self.company_id.l10n_pe_edi_test_env:
            return 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService?wsdl'
        return self._l10n_pe_edi_get_sunat_wsdl()

    @api.model
    def _l10n_pe_edi_response_code(self, cdr_tree):
        """
        Parse EDI response codes from either Estela (formerly Digiflow) or SUNAT.

        Estela format: faultstring contains the code directly (e.g., "2800")
        SUNAT format: faultcode contains the code after a dot (e.g., "soap-env:Client.2800")

        Returns:
            tuple: (message_element, code) where code is False if no error
        """
        if (message := cdr_tree.find('.//{*}message')) is not None:
            message_element = message
        else:
            message_element = cdr_tree.find('.//{*}faultstring')
        code_element = cdr_tree.find('.//{*}faultcode')
        if code_element is None:  # faultcode is only when it is errored
            return message_element, False
        # Try SUNAT format first (faultcode with dot notation)
        code_parts = code_element.text.split('.')
        if len(code_parts) == 2:
            code = code_parts[1]
        else:
            # Fall back to Estela format (code in faultstring)
            faultstring_element = cdr_tree.find('.//{*}faultstring')
            code = faultstring_element.text if faultstring_element is not None else False
        return message_element, code

    @api.model
    def _l10n_pe_edi_decode_soap_response(self, soap_response):
        """
        Parse the SOAP response returned by any of the endpoints (IAP, Estela (formerly Digiflow) or SUNAT)
        for any of the SOAP operations (sendBill, getStatus, sendSummary, getStatusCdr),
        and extract, if they exist, the error, the response code, the CDR, etc.

        Returns a dict which can contain the following fields:
        'error': Description of the error (string with HTML format), if the response was a SOAP fault.
        'code': SOAP response code (a string), if one was provided.
        'message': Description of the response status (a string), if one was provided.
        'number': Ticket number (a string) returned by the getSummary endpoint.
        'cdr': the CDR (bytes with XML format), if it was provided.
        """
        try:
            response_tree = etree.fromstring(soap_response)
        except etree.LxmlError:
            return {'error': self._l10n_pe_edi_get_general_error_messages()['L10NPE08'], 'retry': True}
        if response_tree.find('.//{*}Fault') is not None:
            message_element, code = self._l10n_pe_edi_response_code(response_tree)
            message = message_element.text
            error_messages_map = self._l10n_pe_edi_get_cdr_error_messages()
            error_message = '%s<br/><br/><b>%s</b><br/>%s|%s' % (
                error_messages_map.get(code, self.env._("We got an error response from the OSE. ")),
                self.env._('Original message:'),
                html_escape(code),
                html_escape(message),
            )
            return {'error': error_message, 'code': code, 'message': message}
        if response_tree.find('.//{*}sendBillResponse') is not None:
            cdr_b64 = response_tree.find('.//{*}applicationResponse').text
            cdr = self._l10n_pe_edi_unzip_edi_document(base64.b64decode(cdr_b64))
            return {'cdr': cdr}
        if response_tree.find('.//{*}getStatusResponse') is not None:
            code = response_tree.find('.//{*}statusCode').text
            if response_tree.find('.//{*}content') is not None:
                cdr_b64 = response_tree.find('.//{*}content').text
                cdr = self._l10n_pe_edi_unzip_edi_document(base64.b64decode(cdr_b64))
            else:
                cdr = None
            return {'code': code, 'cdr': cdr}
        if response_tree.find('.//{*}sendSummaryResponse') is not None:
            ticket = response_tree.find('.//{*}ticket').text
            return {'number': ticket}
        if response_tree.find('.//{*}getStatusCdrResponse') is not None:
            code = response_tree.find('.//{*}statusCode').text
            message = response_tree.find('.//{*}statusMessage').text
            if response_tree.find('.//{*}content') is not None:
                cdr_b64 = response_tree.find('.//{*}content').text
                cdr = self._l10n_pe_edi_unzip_edi_document(base64.b64decode(cdr_b64))
                return {'code': code, 'message': message, 'cdr': cdr}
            error_messages_map = self._l10n_pe_edi_get_cdr_error_messages()
            error_message = '%s<br/><br/><b>%s</b><br/>%s|%s' % (
                error_messages_map.get(code, self.env._("We got an error response from the OSE. ")),
                self.env._('Original message:'),
                html_escape(code),
                html_escape(message),
            )
            # No 'content' means SUNAT hasn't finished processing/generating the CDR yet: we don't
            # have a definitive answer, so this is worth retrying automatically.
            return {'error': error_message, 'retry': True, 'code': code, 'message': message}
        return {'error': self._l10n_pe_edi_get_general_error_messages()['L10NPE08'], 'retry': True}

    def _l10n_pe_edi_parse_cancel_soap(self, soap_response):
        soap_response_decoded = self._l10n_pe_edi_decode_soap_response(soap_response) if soap_response else {}

        if soap_response_decoded.get('error'):
            return {'message': soap_response_decoded['error'], 'level': 'danger', 'code': soap_response_decoded.get('code')}

        if not soap_response_decoded.get('cdr'):
            # The server can respond with an error code 98 which means that the cancellation has
            # not yet finished processing. In this case, the response will not contain a CDR.
            # - see https://fe-primer.greenter.dev/docs/baja#envio-a-sunat
            code = soap_response_decoded.get('code')
            error_messages_map = self._l10n_pe_edi_get_cdr_error_messages()
            error_message = '%s<br/><br/><b>%s</b>%s' % (
                error_messages_map.get(code, self.env._("We got an error response from the OSE. ")),
                self.env._('SOAP status code: '),
                html_escape(code),
            )
            error_dict = {'message': error_message, 'level': 'info'}
            if code == '98':
                error_dict.update({
                    'action_call': ('account.move', 'button_request_cancel', self.ids),
                    'action_text': self.env._("Retry cancellation"),
                })
            return error_dict
        cdr = soap_response_decoded['cdr']
        cdr_status = self._l10n_pe_edi_extract_cdr_status(cdr)

        if cdr_status['code'] != '0':
            return {'message': cdr_status['description'], 'level': 'danger'}

        return {'success': True, 'cdr': cdr}

    def _l10n_pe_edi_check_move_constraints(self):
        res = {}
        self.ensure_one()
        if not self.company_id.vat:
            res['l10n_pe_no_company_vat'] = {'message': self.env._("VAT number is missing on company %s", self.company_id.display_name), 'level': 'danger'}
        if not self.commercial_partner_id.l10n_pe_sunat_id_value:
            res['l10n_pe_no_partner_vat'] = {'message': self.env._("An identification number is missing on partner %s", self.commercial_partner_id.display_name), 'level': 'danger'}

        lines = self.invoice_line_ids.filtered(lambda line: line.display_type not in ('line_section', 'line_subsection', 'line_note'))

        # Withholding taxes must be on all invoice lines or none. (Note they are the only type of IGV taxes that can be joined with other IGV taxes.
        withholding_tax_group_id = self.env['account.chart.template'].with_company(self.company_id).ref('tax_group_igv_withholding', raise_if_not_found=False)
        if withholding_tax_group_id and len({withholding_tax_group_id in line.tax_ids.tax_group_id for line in lines}) != 1:
            res['l10n_pe_mixed_withholding'] = {'message': self.env._("All invoice lines must have the same withholding setting when the customer is a withholding agent. You cannot mix lines with withholding and lines without withholding on the same invoice."), 'level': 'danger'}

        for line in lines:
            taxes = line.tax_ids
            if len(taxes) > 1 and len(taxes.filtered(lambda t: t.tax_group_id.l10n_pe_edi_code == 'IGV' and t.tax_group_id != withholding_tax_group_id)) > 1:
                res['l10n_pe_multiple_igv'] = {'message': self.env._("You can't have more than one IGV tax per line to generate a legal invoice in Peru"), 'level': 'danger'}
                break
        if any(not line.tax_ids for line in self.invoice_line_ids if line.display_type not in ('line_section', 'line_subsection', 'line_note') and line._check_edi_line_tax_required()):
            res['l10n_pe_missing_tax'] = {'message': self.env._("Taxes need to be assigned on all invoice lines"), 'level': 'danger'}

        if self.move_type == 'out_refund' and any(line.quantity < 0 or line.price_total < 0 for line in self.invoice_line_ids if line.display_type not in ('line_section', 'line_subsection', 'line_note')):
            res['l10n_pe_negative_line'] = {'message': self.env._("The credit note cannot have negative quantities or amounts on any line"), 'level': 'danger'}

        # When this condition is met in `_l10n_pe_edi_get_spot` we will need this bank account.
        # As the mentioned method is meant to be run by a CRON, the user won't be able to see the error hence we raise it here.
        max_percent = max(self.invoice_line_ids.mapped('product_id.l10n_pe_withhold_percentage'), default=0)
        need_national_bank_account = not (not max_percent or not self.l10n_pe_edi_operation_type in ['1001', '1002', '1003', '1004'] or self.move_type == 'out_refund')
        if need_national_bank_account:
            national_bank_account = self.company_id.bank_ids.filtered(lambda b: b._is_peruvian_national_bank_account())
            if not national_bank_account:
                res['l10n_pe_no_configured_bank'] = {'message': self.env._("To generate the electronic document with this invoice, the bank account at the national bank will be needed.\nPlease configure it.\n"), 'level': 'danger'}

        if self.l10n_pe_edi_is_required and self.l10n_latam_document_type_id.code in ('07', '08') and any(self.invoice_line_ids.mapped('discount')):
            res['l10n_pe_no_discount_on_credit_debit'] = {'message': self.env._("Credit and Debit notes with discounts are not allowed in SUNAT. Please adjust the lines to confirm the document."), 'level': 'danger'}
        return res

    def _l10n_pe_edi_transform_error(self, api_error):
        allowed_keys = ['message', 'level', 'action_call', 'action_text', 'action']
        cleaned_api_error = {k: v for k, v in api_error.items() if k in allowed_keys}

        cleaned_api_error['message'] = html2plaintext(cleaned_api_error['message'])
        return {
            "edi_error": {
                "message": self.env._("There was an error while sending the document to SUNAT."),
                "level": "danger",
                "action_text": self.env._("View Document"),
                "action": {'type': 'ir.actions.act_url', 'url': f'/web/content/account.move/{self.id}/l10n_pe_edi_content'},
                **cleaned_api_error,
            },
        }

    @api.model
    def _l10n_pe_edi_get_sunat_wsdl(self):
        """This method will handle the SUNAT WSDL, in production we have an error while using zeep because of one
        definition that has no binding, so, we just store the XML of the service and remove the unvalid data.
        Reported https://github.com/mvantellingen/python-zeep/issues/924
        """
        return io.BytesIO(b'''
            <wsdl:definitions xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/" xmlns:soap11="http://schemas.xmlsoap.org/wsdl/soap/" xmlns:soap12="http://schemas.xmlsoap.org/wsdl/soap12/" xmlns:http="http://schemas.xmlsoap.org/wsdl/http/" xmlns:mime="http://schemas.xmlsoap.org/wsdl/mime/" xmlns:wsp="http://www.w3.org/ns/ws-policy" xmlns:wsp200409="http://schemas.xmlsoap.org/ws/2004/09/policy" xmlns:wsp200607="http://www.w3.org/2006/07/ws-policy" xmlns:ns0="http://service.gem.factura.comppago.registro.servicio.sunat.gob.pe/" xmlns:ns1="http://service.sunat.gob.pe" xmlns:ns2="http://www.datapower.com/extensions/http://schemas.xmlsoap.org/wsdl/soap12/" targetNamespace="http://service.gem.factura.comppago.registro.servicio.sunat.gob.pe/">
            <wsdl:import location="https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService?ns1.wsdl" namespace="http://service.sunat.gob.pe"/>
            <wsdl:binding name="BillServicePortBinding" type="ns1:billService">
                <soap11:binding transport="http://schemas.xmlsoap.org/soap/http" style="document"/>
                <wsdl:operation name="getStatus">
                <soap11:operation soapAction="urn:getStatus" style="document"/>
                <wsdl:input name="getStatusRequest">
                    <soap11:body use="literal"/>
                </wsdl:input>
                <wsdl:output name="getStatusResponse">
                    <soap11:body use="literal"/>
                </wsdl:output>
                </wsdl:operation>
                <wsdl:operation name="sendBill">
                <soap11:operation soapAction="urn:sendBill" style="document"/>
                <wsdl:input name="sendBillRequest">
                    <soap11:body use="literal"/>
                </wsdl:input>
                <wsdl:output name="sendBillResponse">
                    <soap11:body use="literal"/>
                </wsdl:output>
                </wsdl:operation>
                <wsdl:operation name="sendPack">
                <soap11:operation soapAction="urn:sendPack" style="document"/>
                <wsdl:input name="sendPackRequest">
                    <soap11:body use="literal"/>
                </wsdl:input>
                <wsdl:output name="sendPackResponse">
                    <soap11:body use="literal"/>
                </wsdl:output>
                </wsdl:operation>
                <wsdl:operation name="sendSummary">
                <soap11:operation soapAction="urn:sendSummary" style="document"/>
                <wsdl:input name="sendSummaryRequest">
                    <soap11:body use="literal"/>
                </wsdl:input>
                <wsdl:output name="sendSummaryResponse">
                    <soap11:body use="literal"/>
                </wsdl:output>
                </wsdl:operation>
            </wsdl:binding>
            <wsdl:service name="billService">
                <wsdl:port name="BillServicePort" binding="ns0:BillServicePortBinding">
                <soap11:address location="https://e-factura.sunat.gob.pe:443/ol-ti-itcpfegem/billService"/>
                </wsdl:port>
                <wsdl:port name="BillServicePort.0" binding="ns2:BillServicePortBinding">
                <soap12:address location="https://e-factura.sunat.gob.pe:443/ol-ti-itcpfegem/billService"/>
                </wsdl:port>
                <wsdl:port name="BillServicePort.3" binding="ns0:BillServicePortBinding">
                <soap11:address location="https://e-factura.sunat.gob.pe:443/ol-ti-itcpfegem/billService"/>
                </wsdl:port>
            </wsdl:service>
            </wsdl:definitions>''')

    @api.model
    def _l10n_pe_edi_get_general_error_messages(self):
        return {
            'L10NPE08': self.env._("There was an error in the connection or the response from the OSE server. Please try again later."),
            'L10NPE17': self.env._("There are problems with the connection to the IAP server. "
                            "Please try again in a few minutes."),
            'L10NPE18': self.env._("The URL provided for the IAP server is wrong, please go to  Settings --> System "
                            "Parameters and add the right URL to parameter l10n_pe_edi.endpoint."),
        }

    @api.model
    def _l10n_pe_edi_get_cdr_error_messages(self):
        """The codes from the response of the CDR  and the service we are consulting must be processed to find if the
        message is common, if it is, we will set a friendly message giving instructions on how to fix the
        error/warning."""
        return {
            '2800': self.env._("The type of identity document used for the client is not valid. Review the type of document "
                        "used in the client and change it according to the case of the document to be created. For "
                        "invoices it's only valid to use RUC as identity document."),
            '2801': self.env._("The VAT you use for the customer is a DNI type, to be a valid DNI it must be the exact length "
                        "of 8 digits."),
            '2315': self.env._("The cancellation reason field should not be empty when cancelling the invoice, you must return "
                        "this invoice to Draft, edit the document and enter a cancellation reason."),
            '3105': self.env._("One or more lines of this document do not have taxes assigned, to solve this you must return "
                        "the document to the Draft state and place taxes on the lines that do not have them."),
            '4332': self.env._("One or more products do not have the UNSPSC code configured, to avoid this warning you must "
                        "configure a code for this product. This warning does not invalidate the document."),
            '2017': self.env._("For invoices, the customer's identity document must be RUC. Check that the client has a valid "
                        "RUC and the type of document is RUC."),
            '3206': self.env._("The type of operation is not valid for the type of document you are trying to create. The "
                        "document must return to Draft state and change the type of operation."),
            '2022': self.env._("The name of the Partner must contain at least 2 characters and must not contain special characters."),
            '151': self.env._("The name of the file depends on the sequence in the journal, please go to the journal and "
                       "configure the shortcode as LLL- (three (3) letters plus a dash and the 3 letters must be UPPERCASE.)"),
            '156': self.env._("The zip file is corrupted, check again if the file trying to access is not damaged."),
            '2119': self.env._("The invoice related to this Credit Note has not been reported, go to the invoice related and "
                        "sign it in order to generate this Credit Note."),
            '2120': self.env._("The invoice related to this Credit Note has been cancelled, set this document to draft and "
                        "cancel it."),
            '2209': self.env._("The invoice related to this Debit Note has not been reported, go to the invoice related and "
                        "sign it in order to generate this Debit Note"),
            '2207': self.env._("The invoice related to this Debit Note has been cancelled, set this document to draft and "
                        "cancel it."),
            '001': self.env._("This invoice has been validated by the OSE and we can not allow set it to draft, please try "
                       "to revert it with a credit not or cancel it and create a new one instead."),
            '1033': self.env._("This document already exists on the OSE side.  Check if you gave a proper unique name to your "
                        "document. "),
            '1034': self.env._("Check that the VAT set in the company is correct, this error generally happen when you did "
                        "not set a proper VAT in the company, go to company form and set it properly.."),
            '2371': self.env._("Check your tax configuration, go to Configuration -> Taxes and set the field "
                        "'Affectation reason' to set it by default or set the proper value in the field Affect. Reason "
                        "in the line"),
            '2204': self.env._("The document type of the invoice related is not the same of this document. Check the "
                        "document type of the invoice related and set this document with that document type. In case of "
                        "this document being posted and having a number already, reset to draft and cancel it, this "
                        "document will be cancelled locally and not reported."),
            '2116': self.env._("The document type of the invoice related is not the same of this document. Check the "
                        "document type of the invoice related and set this document with that document type. In case of "
                        "this document being posted and having a number already, reset to draft and cancel it, this "
                        "document will be cancelled locally and not reported."),
            '3034': self.env._("You need to configure the account for 'Banco de la Nación'. go to the Other Info setting"
                        " on this invoice and select the Recipient Bank field, If you want to set it by default go to "
                        "the partner related to your company and set the bank account related to the Banco de la "
                        "Nación"),
            '3128': self.env._("As you have a document that must be detracted (withheld) which mean a document over 700 "
                        "Soles With services you must select on the 'Operation Type field the correct code 1001 "
                        "for example"),
            '154': self.env._("Your RUC is not linked to Estela (formerly Digiflow) as OSE, please make sure you have "
                       "followed this process in the SUNAT portal:\n"
                       "1. Linked Estela (formerly Digiflow) as OSE.\n"
                       "2. Authorize Estela (formerly Digiflow) as PSE.\n"
                       "Reference: \n"
                       "https://www.odoo.com/documentation/latest/applications/finance/accounting/fiscal_localizations/localizations/peru.html#what-do-you-need-to-do"),
            '98': self.env._("The cancellation request has not yet finished processing by SUNAT. Please retry in a few minutes."),
            '2640': self.env._("The tax application is incorrect for free invoice."),
            '3020': self.env._("Verify that the taxes are configured correctly: for free invoice, make sure to include "
                        "only the taxes applicable to free operations and the free billing legend in the Peruvian EDI tab."),
            '3294': self.env._("Verify that the taxes are configured correctly: for free invoice, make sure to include "
                        "only the taxes applicable to free operations and the free billing legend in the Peruvian EDI tab."),
        }
