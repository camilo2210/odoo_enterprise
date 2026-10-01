import re
from base64 import b64encode
from dateutil.relativedelta import relativedelta
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qsl, urlsplit

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import freeze_time, tagged
from odoo.tests.common import MockHTTPClient
from odoo.tools import file_open

from odoo.addons.l10n_tr_nilvera_einvoice.tests.test_xml_ubl_tr_common import (
    TestUBLTRCommon,
)

COMPANY_VAT = '3297552117'
ERRORENOUS_ALIAS = 'erroneous_alias'
EINVOICE_PARTNER_VAT = '1729171602'
EARCHIVE_PARTNER_VAT = '17291716060'
SERVER_ERROR_ALIAS = 'server_error_alias'
UNAUTHORIZED_ALIAS = 'unauthorized_alias'
UUID_INVALID_STATUS = 'uuid_with_invalid_status_code'
UUID_UNKNOWN_STATUS = 'uuid_with_unknown_status_code'
UUID_INVALID_INVOICE = 'uuid_invalid_invoice'
UUID_VALID_INVOICE = 'uuid_valid_invoice'

STATUS_ENDPOINT = re.compile(r'/(?:einvoice|earchive)/(?:sale|invoices)/([\w-]+)/Status')
PDF_ENDPOINT = re.compile(r'/(?:einvoice|earchive)/(?:sale|invoices)/([\w-]+)/pdf')


def mocked_pdf():
    with file_open('l10n_tr_nilvera_einvoice/tests/test_files/fetching/invoice.pdf', 'rb') as pdf:
        return b64encode(pdf.read()).decode()


def nilvera_status(request):
    if request.method == 'POST' and 'Send/Xml' in request.url:
        if UNAUTHORIZED_ALIAS in request.url:
            return 401
        if SERVER_ERROR_ALIAS in request.url:
            return 500
        if ERRORENOUS_ALIAS in request.url:
            return 422
    return 200


def nilvera_body(request):
    """Return the JSON body Nilvera would answer with for `request`.

    The XML and PDF endpoints return their payload as a JSON string, which
    NilveraClient.request() decodes back to that string.
    """
    path = urlsplit(request.url).path

    if request.method == 'GET' and 'Check/TaxNumber' in request.url:
        if EINVOICE_PARTNER_VAT in request.url:
            return [{
                'DocumentType': 'Invoice',
                'Name': 'urn:mail:salt@bae.com',
                'TaxNumber': EINVOICE_PARTNER_VAT,
                'Title': 'Salt Bae LLC',
                'Type': 'OZEL',
            }]
        if COMPANY_VAT in request.url:
            return [{
                'TaxNumber': 'text',
                'Title': 'text',
                'FirstCreatedTime': '2025-06-23',
                'CreationTime': '2025-06-23',
                'DocumentType': 'text',
                'Name': 'text',
                'Type': 'text',
            }]
        if EARCHIVE_PARTNER_VAT in request.url:
            return []

    if request.method == 'GET' and (match := STATUS_ENDPOINT.fullmatch(path)):
        if match.group(1) == UUID_INVALID_STATUS:
            status_code = "boop"
        elif match.group(1) == UUID_UNKNOWN_STATUS:
            # e-Archive invoices stay unknown until GİB generates its report at 20:00 GMT+3.
            status_code = "unknown"
        else:
            status_code = "succeed"
        return {"InvoiceStatus": {"Code": status_code, "Description": "text", "DetailDescription": "text"}}

    if request.method == 'POST' and 'Send/Xml' in request.url:
        if ERRORENOUS_ALIAS in request.url:
            return {
                "Message": "HATALI ISTEK",
                "Errors": [{
                    "Code": 2000,
                    "Description": "Yeterli Kontörünüz Bulunmamaktadır.",
                    "Detail": "Yeterli Kontörünüz Bulunmamaktadır. Lütfen Kontör Alımı Yapınız.",
                }],
            }
        return {"UUID": "00aac88a-576b-4a62-98b5-ed34fe4d187d", "InvoiceNumber": ""}

    if request.method == 'GET' and PDF_ENDPOINT.fullmatch(path):
        return mocked_pdf()

    if request.method == 'GET' and '/einvoice/Purchase' in path:
        if path.endswith('/xml'):
            with file_open('l10n_tr_nilvera_einvoice/tests/test_files/fetching/invoice.xml', 'rb') as xml:
                return xml.read().decode()
        if path.endswith('/pdf'):
            return mocked_pdf()
        return {'TotalPages': 1, 'Content': [{'UUID': 'invoice_uuid', 'CreatedDate': '2025-03-05'}]}

    return {}


def mock_nilvera():
    return MockHTTPClient(
        matcher=lambda request: 'nilvera.com' in request.url,
        return_status=nilvera_status,
        return_json=nilvera_body,
    )


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTRNilveraMockedRequests(TestUBLTRCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with mock_nilvera(), patch.object(cls.env.cr, 'commit', autospec=True):
            cls.einvoice_partner._check_nilvera_customer()
            cls.earchive_partner._check_nilvera_customer()
        cls.env['account.journal'].create({
            'name': 'TR Journal',
            'code': 'TRJ',
            'type': 'purchase',
            'company_id': cls.company.id,
        })

    def setUp(self):
        super().setUp()
        self.nilvera = self.enterContext(mock_nilvera())

    def _find_requests(self, method, path, since=0):
        return [
            request
            for request in self.nilvera.calls[since:]
            if request.method == method and urlsplit(request.url).path == path
        ]

    def test_amount_in_words_rounds_subunit(self):
        note = self.env['account.edi.xml.ubl.tr']._l10n_tr_get_amount_integer_partn_text_note(
            3989.33, self.env.ref('base.TRY'),
        )
        self.assertEqual(note, 'YALNIZ : ÜÇBINDOKUZYÜZSEKSENDOKUZ TRY OTUZÜÇ KURUŞ')

    def test_which_service_to_call(self):
        _, invoice = self._generate_invoice_xml(self.einvoice_partner, include_invoice=True)

        invoices_data = {
            invoice: {
                **self.env['account.move.send']._get_default_sending_settings(invoice),
            },
        }

        with patch('odoo.addons.l10n_tr_nilvera_einvoice.models.account_move.AccountMove._l10n_tr_nilvera_submit_einvoice') as mock_submit_einvoice, \
             patch('odoo.addons.l10n_tr_nilvera_einvoice.models.account_move.AccountMove._l10n_tr_nilvera_submit_earchive') as mock_submit_earchive:
            self.env['account.move.send']._call_web_service_before_invoice_pdf_render(invoices_data)
            mock_submit_einvoice.assert_called_once()
            mock_submit_earchive.assert_not_called()

            # Reset the alias to empty for the next test
            invoice.partner_id.l10n_tr_nilvera_customer_alias_id = self.env['l10n_tr.nilvera.alias']
            invoice.partner_id.vat = False
            mock_submit_einvoice.reset_mock()
            mock_submit_earchive.reset_mock()

            self.env['account.move.send']._call_web_service_before_invoice_pdf_render(invoices_data)
            mock_submit_earchive.assert_called_once()
            mock_submit_einvoice.assert_not_called()

    def test_submit_einvoice(self):
        xml, invoice = self._generate_invoice_xml(self.einvoice_partner, include_invoice=True)
        wrapped_xml = BytesIO(xml)
        wrapped_xml.name = 'invoice.xml'
        invoice._l10n_tr_nilvera_submit_einvoice(wrapped_xml, self.einvoice_partner.l10n_tr_nilvera_customer_alias_id.name)

        requests_made = self._find_requests('POST', '/einvoice/Send/Xml')
        self.assertEqual(len(requests_made), 1)
        self.assertEqual(urlsplit(requests_made[0].url).query, 'Alias=urn%3Amail%3Asalt%40bae.com')
        self.assertIn(b'invoice.xml', requests_made[0].body)
        self.assertTrue(invoice.is_move_sent)
        self.assertEqual(invoice.l10n_tr_nilvera_send_status, 'sent')

    def test_submit_earchive(self):
        xml, invoice = self._generate_invoice_xml(self.earchive_partner, include_invoice=True)
        wrapped_xml = BytesIO(xml)
        wrapped_xml.name = 'invoice.xml'
        invoice._l10n_tr_nilvera_submit_earchive(wrapped_xml)

        requests_made = self._find_requests('POST', '/earchive/Send/Xml')
        self.assertEqual(len(requests_made), 1)
        self.assertIn(b'invoice.xml', requests_made[0].body)
        self.assertTrue(invoice.is_move_sent)
        self.assertEqual(invoice.l10n_tr_nilvera_send_status, 'sent')

    def test_submit_einvoice_errors(self):
        xml, invoice = self._generate_invoice_xml(self.einvoice_partner, include_invoice=True)
        wrapped_xml = BytesIO(xml)
        wrapped_xml.name = 'invoice.xml'
        error_cases = [
            (UNAUTHORIZED_ALIAS, "Oops, seems like you're unauthorised to do this. Try another API key with more rights or contact Nilvera."),
            (SERVER_ERROR_ALIAS, "Server error from Nilvera, please try again later."),
            (ERRORENOUS_ALIAS, "The invoice couldn't be sent due to the following errors:\n\n2000 - You do not have sufficient credits:\nYeterli Kontörünüz Bulunmamaktadır. Lütfen Kontör Alımı Yapınız.\n"),
        ]

        for alias, expected_error in error_cases:
            with self.assertRaises(UserError) as context:
                invoice._l10n_tr_nilvera_submit_einvoice(wrapped_xml, alias)
            self.assertEqual(str(context.exception), expected_error)

    def test_fetch_status(self):
        _, invoice = self._generate_invoice_xml(self.einvoice_partner, include_invoice=True)
        invoice._l10n_tr_nilvera_get_submitted_document_status()

        self.assertEqual(invoice.l10n_tr_nilvera_send_status, 'succeed')

    def test_fetch_status_fetches_pdf(self):
        # Syncing the status must also bring back the official PDF once the invoice succeeded.
        _, invoice = self._generate_invoice_xml(self.einvoice_partner, include_invoice=True)

        invoice.l10n_tr_nilvera_fetch_move_status()

        self.assertEqual(invoice.l10n_tr_nilvera_send_status, 'succeed')
        self.assertTrue(self._find_requests('GET', f'/einvoice/sale/{invoice.l10n_tr_nilvera_uuid}/pdf'))
        self.assertTrue(invoice.l10n_tr_nilvera_pdf_id)

    def test_fetch_status_fetches_pdf_earchive(self):
        _, invoice = self._generate_invoice_xml(self.earchive_partner, include_invoice=True)

        invoice.l10n_tr_nilvera_fetch_move_status()

        self.assertEqual(invoice.l10n_tr_nilvera_send_status, 'succeed')
        self.assertTrue(self._find_requests('GET', f'/earchive/invoices/{invoice.l10n_tr_nilvera_uuid}/pdf'))
        self.assertTrue(invoice.l10n_tr_nilvera_pdf_id)

    def test_fetch_status_unknown_no_pdf(self):
        # e-Archive invoices remain unknown until the GİB report is generated, no PDF to fetch yet.
        _, invoice = self._generate_invoice_xml(self.earchive_partner, include_invoice=True)
        invoice.l10n_tr_nilvera_uuid = UUID_UNKNOWN_STATUS

        invoice.l10n_tr_nilvera_fetch_move_status()

        self.assertEqual(invoice.l10n_tr_nilvera_send_status, 'unknown')
        self.assertFalse(self._find_requests('GET', f'/earchive/invoices/{UUID_UNKNOWN_STATUS}/pdf'))

    def test_fetch_status_skips_existing_pdf(self):
        _, invoice = self._generate_invoice_xml(self.einvoice_partner, include_invoice=True)
        invoice.l10n_tr_nilvera_fetch_move_status()
        self.assertTrue(invoice.l10n_tr_nilvera_pdf_id)
        already_made = len(self.nilvera.calls)

        invoice.l10n_tr_nilvera_fetch_move_status()

        self.assertFalse(self._find_requests('GET', f'/einvoice/sale/{invoice.l10n_tr_nilvera_uuid}/pdf', since=already_made))

    def test_get_pdf_earchive(self):
        # E-archive PDF retrieval must use the "invoices" resource, not the e-invoice "sale" one.
        _, invoice = self._generate_invoice_xml(self.earchive_partner, include_invoice=True)
        invoice.l10n_tr_nilvera_send_status = 'succeed'

        invoice.l10n_tr_nilvera_get_pdf()

        self.assertTrue(self._find_requests('GET', f'/earchive/invoices/{invoice.l10n_tr_nilvera_uuid}/pdf'))
        self.assertTrue(invoice.l10n_tr_nilvera_pdf_id)

    def test_fetch_invalid_status(self):
        _, invoice = self._generate_invoice_xml(self.einvoice_partner, include_invoice=True)
        invoice.l10n_tr_nilvera_uuid = UUID_INVALID_STATUS

        invoice._l10n_tr_nilvera_get_submitted_document_status()

        self.assertIn(
            invoice.message_ids[0].preview,
            "The invoice status couldn't be retrieved from Nilvera.",
        )

    def test_cancel_earchive(self):
        _, invoice = self._generate_invoice_xml(self.earchive_partner, include_invoice=True)
        invoice.l10n_tr_nilvera_send_status = 'sent'

        invoice.button_cancel_earchive()

        requests_made = self._find_requests('PUT', f'/earchive/Invoices/{invoice.l10n_tr_nilvera_uuid}/Cancel')
        self.assertEqual(len(requests_made), 1)
        self.assertEqual(invoice.state, 'cancel')
        self.assertEqual(invoice.l10n_tr_nilvera_send_status, 'cancelled')
        self.assertIn("Cancellation request created on Nilvera.", invoice.message_ids[0].body)

    def test_cancel_earchive_invalid_status(self):
        _, invoice = self._generate_invoice_xml(self.earchive_partner, include_invoice=True)

        with self.assertRaises(UserError) as error:
            invoice.button_cancel_earchive()

        self.assertEqual(
            str(error.exception),
            "Only e-Archive invoices that have been sent successfully to Nilvera can be cancelled.",
        )

    @freeze_time('2025-03-05')
    def test_fetching_einvoices(self):
        with patch.object(self.env.cr, 'commit', autospec=True):
            self.env['account.move']._l10n_tr_nilvera_get_documents()
            self.env['account.move']._l10n_tr_nilvera_get_documents()

        list_calls = self._find_requests('GET', '/einvoice/Purchase')
        self.assertEqual(len(list_calls), 2)
        # EndDate is adjusted to match the Europe/Istanbul timezone (UTC+3).
        self.assertEqual(dict(parse_qsl(urlsplit(list_calls[0].url).query)), {
            'StatusCode': 'succeed',
            'StartDate': str(fields.Datetime.now() - relativedelta(months=1)),
            'EndDate': '2025-03-05T03:00:00',
            'DateFilterType': 'CreatedDate',
            'SortColumn': 'CreationDateTime',
            'SortType': 'ASC',
            'Page': '1',
        })
        self.assertEqual(parse_qsl(urlsplit(list_calls[1].url).query)[1], ('StartDate', str(fields.Datetime.now())))
        self.assertTrue(self._find_requests('GET', '/einvoice/Purchase/invoice_uuid/xml'))
        self.assertTrue(self._find_requests('GET', '/einvoice/Purchase/invoice_uuid/pdf'))

        invoice = self.env['account.move'].search([('l10n_tr_nilvera_uuid', '=', 'invoice_uuid')])
        self.assertEqual(len(invoice), 1)
        self.assertFalse(invoice.attachment_ids)
        self.assertTrue(invoice.ubl_cii_xml_id)  # XML file used at import
        self.assertTrue(invoice.l10n_tr_nilvera_pdf_id)
        self.assertTrue(
            invoice.l10n_tr_nilvera_pdf_id.raw.content.startswith(b'%PDF-'),
            "PDF attachment must contain decoded PDF bytes, not base64 text",
        )
