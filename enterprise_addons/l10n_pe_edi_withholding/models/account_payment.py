import base64

from lxml import etree, objectify
from requests.exceptions import InvalidSchema, InvalidURL

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import BinaryBytes, html2plaintext

from odoo.addons.iap.tools.iap_tools import iap_jsonrpc


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_edi_status = fields.Selection(
        selection=[
            ('to_send', 'To Send'),
            ('sent', 'Sent'),
            ('cancelled', 'Cancelled'),
        ],
        string="EDI Status",
        copy=False,
    )
    l10n_pe_edi_warnings = fields.Json(
        string="EDI Warnings",
        readonly=True,
        copy=False,
    )
    l10n_pe_edi_attachment_file = fields.Binary(
        string="EDI Attachment",
        attachment=True,
        copy=False,
    )
    l10n_pe_edi_retention_number = fields.Char(
        string="Retention Number",
        related='withholding_line_ids.name',
        readonly=True,
    )
    l10n_pe_edi_is_required = fields.Boolean(
        string="PE EDI Required",
        compute='_compute_l10n_pe_edi_is_required',
    )

    @api.depends('state', 'withhold', 'country_code')
    def _compute_l10n_pe_edi_is_required(self):
        for payment in self:
            payment.l10n_pe_edi_is_required = (
                payment.state in ('paid', 'reconciled')
                and payment.withhold != 'payment'
                and payment.country_code == 'PE'
                and payment.l10n_pe_edi_status != 'sent'
            )

    # -------------------------------------------------------------------------
    # XML Generation
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_get_paid_per_bill(self):
        """Return ``{bill.id: amount}`` in the bill's own currency for every
        reconciled bill, reflecting how much of that bill this payment settled
        (supports partial payments and multi-bill reconciliations).
        """
        self.ensure_one()
        result = {}
        bill_ids = set(self.reconciled_bill_ids.ids)
        for line in self.move_id.line_ids.filtered(lambda l: l.account_id.reconcile):
            for partial in line.matched_debit_ids | line.matched_credit_ids:
                counterpart = (
                    partial.debit_move_id
                    if partial.credit_move_id == line
                    else partial.credit_move_id
                )
                bill_id = counterpart.move_id.id
                if bill_id not in bill_ids:
                    continue
                if partial.debit_move_id == counterpart:
                    amount = partial.debit_amount_currency
                else:
                    amount = partial.credit_amount_currency
                result[bill_id] = result.get(bill_id, 0.0) + amount
        return result

    def _l10n_pe_edi_get_retention_breakdown(self):
        """Per-bill retention breakdown in company currency, shared by the XML
        builder and PDF report so they emit consistent figures. For partial
        payments, distribution is based on the amount reconciled against each
        bill rather than the bill totals.
        """
        self.ensure_one()
        company = self.company_id
        company_currency = company.currency_id
        retention_total_pen = sum(
            line.comodel_currency_id._convert(line.amount, company_currency, company, self.date)
            for line in self.withholding_line_ids
        )
        paid_per_bill = self._l10n_pe_edi_get_paid_per_bill()

        paid_pen = {}
        rates = {}
        for bill in self.reconciled_bill_ids:
            paid_currency = paid_per_bill.get(bill.id, 0.0)
            if bill.currency_id == company_currency:
                rates[bill.id] = 1.0
                paid_pen[bill.id] = paid_currency
            else:
                rate = bill.currency_id._get_conversion_rate(
                    bill.currency_id, company_currency, company, self.date,
                )
                rates[bill.id] = rate
                paid_pen[bill.id] = company_currency.round(paid_currency * rate)
        sum_paid_pen = sum(paid_pen.values())

        breakdown = []
        for bill in self.reconciled_bill_ids:
            amount_pen = paid_pen[bill.id]
            retention_pen = retention_total_pen * (amount_pen / sum_paid_pen) if sum_paid_pen else 0.0
            breakdown.append({
                'bill': bill,
                'bill_paid_currency': paid_per_bill.get(bill.id, 0.0),
                'bill_paid_pen': amount_pen,
                'bill_retention_pen': retention_pen,
                'net_total_paid_pen': amount_pen - retention_pen,
                'exchange_rate': rates[bill.id],
            })
        return breakdown

    def _l10n_pe_edi_generate_retention_bstr(self):
        self.ensure_one()
        builder = self.env['account.edi.xml.ubl_pe_withholding']
        xml_content = builder._export_retention(self)

        # Insert empty UBLExtensions node for signature (removed by dict_to_xml as empty).
        edi_tree = objectify.fromstring(xml_content)
        ubl_version_id_element = edi_tree.find('.//{*}UBLVersionID')[0]
        ubl_extensions_str = self.env['ir.qweb']._render('l10n_pe_edi.ubl_pe_21_ubl_extensions_empty_signature')
        ubl_version_id_element.addprevious(objectify.fromstring(ubl_extensions_str))

        return etree.tostring(edi_tree, xml_declaration=True, encoding='ISO-8859-1', pretty_print=True)

    def _l10n_pe_edi_generate_retention_filename(self):
        # Retentions have a LATAM doc type code of 20
        self.ensure_one()
        return f'{self.company_id.vat}-20-{self.l10n_pe_edi_retention_number}'

    # -------------------------------------------------------------------------
    # EDI Sending
    # -------------------------------------------------------------------------

    def action_l10n_pe_edi_send_retention(self):
        payments_ready_for_sending = self.filtered(lambda p: p.l10n_pe_edi_is_required)
        rest_payments = self - payments_ready_for_sending
        if rest_payments:
            raise UserError(self.env._("The following payments cannot be sent due to missing or invalid information: %s", rest_payments.mapped('name')))

        for payment in payments_ready_for_sending:
            # Validate that at least one bill is reconciled (required by SUNAT)
            if not payment.reconciled_bill_ids:
                payment.l10n_pe_edi_warnings = {
                    'edi_error': {
                        'message': self.env._(
                            "No vendor bills are reconciled with this payment."
                            " The retention document requires at least one referenced bill.",
                        ),
                        'level': 'danger',
                    },
                }
                payment.l10n_pe_edi_status = 'to_send'
                continue

            edi_str = payment._l10n_pe_edi_generate_retention_bstr()
            result = payment._l10n_pe_edi_post_retention(edi_str)

            if result.get('success'):
                payment.l10n_pe_edi_status = 'sent'
                payment.l10n_pe_edi_warnings = False
                attachment = self.env['ir.attachment'].create({
                    'name': f'{payment._l10n_pe_edi_generate_retention_filename()}.zip',
                    'res_model': 'account.payment',
                    'res_id': payment.id,
                    'res_field': 'l10n_pe_edi_attachment_file',
                    'type': 'binary',
                    'raw': result['zip_document'],
                })
                payment.message_post(
                    body=self.env._("Retention document sent successfully."),
                    attachment_ids=attachment.ids,
                )
            else:
                error_message = result.get('message', self.env._("Unknown error"))
                payment.l10n_pe_edi_warnings = {
                    'edi_error': {
                        'message': html2plaintext(error_message),
                        'level': result.get('level', 'danger'),
                    },
                }
                payment.l10n_pe_edi_status = 'to_send'

    def _l10n_pe_edi_post_retention(self, edi_str):
        self.ensure_one()
        AccountMove = self.env['account.move']

        if self.company_id.l10n_pe_edi_provider == 'iap':
            return self._l10n_pe_edi_post_retention_iap(edi_str)

        certificate = self.company_id.sudo().l10n_pe_edi_certificate_id
        if not certificate:
            return {'message': self.env._("No valid certificate found for %s company.", self.company_id.display_name)}

        edi_tree = objectify.fromstring(edi_str)
        edi_tree = AccountMove._l10n_pe_edi_sign(certificate, edi_tree)
        edi_str = etree.tostring(edi_tree, xml_declaration=True, encoding='ISO-8859-1')

        filename = self._l10n_pe_edi_generate_retention_filename()
        zip_edi_str = AccountMove._l10n_pe_edi_zip_edi_document([(f'{filename}.xml', edi_str)])

        credentials = self.company_id._l10n_pe_edi_get_credentials(
            sunat_wsdl=self._l10n_pe_edi_get_retention_sunat_wsdl(),
        )
        soap_response_decoded = AccountMove._l10n_pe_edi_send_bill_sunat_estela(credentials, filename, zip_edi_str)

        return self._l10n_pe_edi_build_retention_result(soap_response_decoded, edi_str, filename)

    def _l10n_pe_edi_post_retention_iap(self, edi_str):
        self.ensure_one()
        AccountMove = self.env['account.move']

        dbuuid, iap_server_url, iap_token = AccountMove._l10n_pe_edi_get_iap_params(self.company_id)
        filename = self._l10n_pe_edi_generate_retention_filename()

        rpc_params = {
            'vat': self.company_id.vat,
            'doc_type': '20',
            'dbuuid': dbuuid,
            'fname': filename,
            'xml': BinaryBytes(edi_str).to_base64(),
            'token': iap_token,
        }

        try:
            result = iap_jsonrpc(iap_server_url + '/iap/l10n_pe_edi/1/send_bill', params=rpc_params, timeout=60)
        except AccessError:
            return {'message': AccountMove._l10n_pe_edi_get_general_error_messages()['L10NPE17']}
        except (InvalidSchema, InvalidURL):
            return {'message': AccountMove._l10n_pe_edi_get_general_error_messages()['L10NPE18']}

        if result.get('message'):
            if result['message'] == 'no-credit':
                return AccountMove._l10n_pe_edi_get_iap_buy_credits_message()
            return {'message': result['message']}

        xml_document = result.get('signed') and AccountMove._l10n_pe_edi_unzip_edi_document(base64.b64decode(result['signed']))

        soap_response = result.get('cdr') and base64.b64decode(result['cdr'])
        soap_response_decoded = AccountMove._l10n_pe_edi_decode_soap_response(soap_response) if soap_response else {}

        return self._l10n_pe_edi_build_retention_result(soap_response_decoded, xml_document, filename)

    @api.model
    def _l10n_pe_edi_build_retention_result(self, soap_response_decoded, xml_document, filename):
        AccountMove = self.env['account.move']
        if soap_response_decoded.get('error'):
            return {'message': soap_response_decoded['error'], 'level': soap_response_decoded.get('level', 'danger')}

        cdr = soap_response_decoded.get('cdr')
        if not cdr:
            return {'message': self.env._("No CDR received.")}

        cdr_status = AccountMove._l10n_pe_edi_extract_cdr_status(cdr)
        if cdr_status['code'] != '0':
            return {'message': cdr_status['description']}

        zip_document = AccountMove._l10n_pe_edi_zip_edi_document([
            (f'{filename}.xml', xml_document),
            (f'R-{filename}.xml', cdr),
        ])
        return {'success': True, 'zip_document': zip_document}

    def _l10n_pe_edi_get_retention_sunat_wsdl(self):
        self.ensure_one()
        if self.company_id.l10n_pe_edi_test_env:
            return 'https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService?wsdl'
        return 'https://e-factura.sunat.gob.pe/ol-ti-itemision-otroscpe-gem/billService?wsdl'
