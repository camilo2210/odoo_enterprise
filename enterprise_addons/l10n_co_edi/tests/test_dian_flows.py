from datetime import datetime, timedelta
from unittest.mock import patch
from markupsafe import Markup
import contextlib

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import freeze_time, tagged
from .common import TestCoEdiCommon


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDianFlows(TestCoEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice = cls._create_move()

    def _send_test_set_async(self):
        self.invoice.company_id.l10n_co_edi_test_environment = True
        self.invoice.company_id.l10n_co_edi_certification_process = True

        # Step 1: SendTestSetAsync
        self._mock_send_and_print(move=self.invoice, response_file='SendTestSetAsync.xml')

        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_pending',
            'message': "<p>Invoice is being processed by the DIAN.</p>",
        }])
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_pending')

    # ==== Get Status Zip ==== #

    def test_get_status_zip_warnings(self):
        """ SendTestSetAsync then GetStatusZip which returns warnings but the document is valid. """
        # Step 1: SendTestSetAsync
        self._send_test_set_async()
        # Step 2: GetStatusZip
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_warnings.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_edi_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_accepted',
            'message': (
                "<p>Procesado Correctamente.</p>"
                "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación BlaBlaBla.</li>"
                "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al BlaBlaBla.</li></ul>"
            ),
        }])
        # checks on the invoice
        self.assertTrue(self.invoice.l10n_co_edi_attachment_id)
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_accepted')

    def test_get_status_zip_habilitation(self):
        """ SendTestSetAsync then GetStatusZip which inform that they passed the habitation process. """
        # Step 1: SendTestSetAsync
        self._send_test_set_async()
        # Step 2: GetStatusZip
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_habilitation.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_edi_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_rejected',
            'message': "<p>Set de prueba con identificador 123456 se encuentra Aceptado.</p>",
        }])
        # checks on the invoice
        self.assertFalse(self.invoice.l10n_co_edi_attachment_id)
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_rejected')

    def test_get_status_zip_pending(self):
        """ SendTestSetAsync then GetStatusZip which responds 'Batch is being processed' (need to check again later)"""
        # Step 1: SendTestSetAsync
        self._send_test_set_async()
        # Step 2: GetStatusZip
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_pending.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_edi_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_pending',
            'message': "<p>Batch en proceso de validación.</p>",
            'show_button_get_status': True,
        }])
        # checks on the invoice
        self.assertFalse(self.invoice.l10n_co_edi_attachment_id)
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_pending')

        # Step 3: GetStatusZip again (this time the document is processed)
        self._mock_get_status_zip(move=self.invoice, response_file='GetStatusZip_warnings.xml')

        # checks on the document
        self.assertEqual(len(self.invoice.l10n_co_edi_document_ids), 1)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': '42424242',
            'state': 'invoice_accepted',
            'message': (
                "<p>Procesado Correctamente.</p>"
                "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación BlaBlaBla.</li>"
                "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al BlaBlaBla.</li></ul>"
            ),
        }])
        # checks on the invoice
        self.assertTrue(self.invoice.l10n_co_edi_attachment_id)
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_accepted')

    # ==== Send Bill Sync ==== #

    def test_send_bill_sync_warnings(self):
        """ SendBillSync returning warnings but the document is valid. """
        self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_warnings.xml')

        self.assertTrue(self.invoice.l10n_co_edi_attachment_id)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message':  (
                "<p>Procesado Correctamente.</p>"
                "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación informado No BlaBlaBla.</li>"
                "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al registrado en el BlaBlaBla.</li></ul>"
            ),
        }])

    def test_send_bill_sync_errors(self):
        """ SendBillSync returning errors blocking the Send & Print flow. """
        error_raised = False
        try:
            self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_errors.xml')
        except UserError as e:
            error_raised = True
            self.assertEqual(e.args[0], "Error(s) when sending the document to the DIAN:\n"
                                        "- Regla: ZB01, Rechazo: Fallo en el esquema XML del archivo")

        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_rejected',
            'message': "<p>Documento con errores en campos mandatorios.</p>"
                       "<ul><li>Regla: ZB01, Rechazo: Fallo en el esquema XML del archivo</li></ul>",
        }])

    def test_send_bill_sync_errors_nsmap(self):
        """ SendBillSync returning errors due to a missing namespace, blocking the Send & Print flow. """
        error_raised = False
        try:
            self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_errors_nsmap.xml')
        except UserError as e:
            error_raised = True
            self.assertEqual(e.args[0], "Error(s) when sending the document to the DIAN:\n- Error al parsear xml. Namespace prefix 'sts' is not defined.")

        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_rejected',
            'message': "<p>Error al parsear xml. Namespace prefix 'sts' is not defined.</p>",
        }])

    def test_send_bill_sync_duplicated_identifier_accepted(self):
        """ SendBillSync returning 'Regla: 90, Rechazo: Documento procesado anteriormente.'
        This means an invoice with the same CUFE has already been accepted by the DIAN.
        The invoice on DIAN has the same partner and issue date than the one being sent,
        therefore it is accepted.
        """
        error_raised = False
        try:
            xml = self.file_read('l10n_co_edi/tests/attachments/invoice_alcohol.xml').content
            with patch(f'{self.document_path}._get_xml_by_document_key', return_value=xml):
                self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_duplicated.xml')
        except UserError:
            error_raised = True

        self.assertFalse(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message': ("<p>Validación contiene errores en campos mandatorios.</p>"
                        "<ul><li>Regla: 90, Rechazo: Documento procesado anteriormente.</li></ul>"),
        }])

    def test_send_bill_sync_duplicated_identifier_rejected(self):
        """ SendBillSync returning 'Regla: 90, Rechazo: Documento procesado anteriormente.'
        This means an invoice with the same CUFE has already been accepted by the DIAN.
        The invoice on DIAN has the same partner but a different issue time than the one
        being sent, therefore it is rejected.
        """
        error_raised = False
        try:
            xml = self.file_read('l10n_co_edi/tests/attachments/invoice_alcohol.xml').content
            # change the issue time in the XML so that the invoice should be rejected
            xml = xml.replace(
                b'<cbc:IssueTime>19:00:00-05:00</cbc:IssueTime>',
                b'<cbc:IssueTime>08:00:00-05:00</cbc:IssueTime>'
            )
            with patch(f'{self.document_path}._get_xml_by_document_key', return_value=xml):
                self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_duplicated.xml')
        except UserError:
            error_raised = True

        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_rejected',
            'message': Markup("<p>Validación contiene errores en campos mandatorios.</p>"
                              "<ul><li>Regla: 90, Rechazo: Documento procesado anteriormente.</li></ul>"),
        }])

    def test_send_bill_sync_second_attempt(self):
        """ First attempt SendBillSync returns errors, second attempt is successful. """
        # 1st attempt (fail)
        self.test_send_bill_sync_errors()

        self.assertFalse(self.invoice.l10n_co_edi_attachment_id)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_rejected',
            'message': "<p>Documento con errores en campos mandatorios.</p>"
                       "<ul><li>Regla: ZB01, Rechazo: Fallo en el esquema XML del archivo</li></ul>",
        }])

        # 2nd attempt (success without errors or warnings)
        with self.patched_document('_parse_errors', []):
            self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_warnings.xml')

        self.assertEqual(len(self.invoice.l10n_co_edi_document_ids), 1)  # no need to keep the rejected documents
        self.assertTrue(self.invoice.l10n_co_edi_attachment_id)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message': "<p>Procesado Correctamente.</p>",
        }])

    def test_send_bill_sync_get_status_error(self):
        """
        The attempt SendBillSync is accepted, but getStatus got a non 200 status code
        => status of the invoice should still be invoice_accepted
        """
        error_raised = False
        try:
            with (self.patched_document('_parse_errors', [])):
                self._mock_send_and_print(move=self.invoice, response_file='SendBillSync_warnings.xml', get_status_code=503)

        except UserError:
            error_raised = True

        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'state': 'invoice_accepted',
        }])

    def test_send_bill_sync_unknown_error(self):
        """ Handle the generic error returned when using wrong certificates (e.g. the demo certificate). """
        error_raised = False
        try:
            self._mock_send_and_print(move=self.invoice, response_file='unknown_error.xml', response_code=500)
        except UserError as e:
            error_raised = True
            self.assertEqual(e.args[0], "Error(s) when sending the document to the DIAN:\n"
                                        "- The creator of this fault did not specify a Reason. "
                                        "(This might be caused by using incorrect certificates)")
        self.assertTrue(error_raised)
        self.assertRecordValues(self.invoice.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_sending_failed',
            'message': "<p>The creator of this fault did not specify a Reason. "
                       "(This might be caused by using incorrect certificates)</p>",
        }])

    def test_send_bill_sync_support_document(self):
        """ Send Support Document. """
        bill = self._create_move(
            move_type='in_invoice',
            invoice_date=datetime.today(),
            journal_id=self.support_document_journal.id,
        )
        with (
            patch(f'{self.utils_path}._build_and_send_request', return_value=self._mocked_response('SendBillSync_warnings.xml', 200)),
            self._disable_get_acquirer_call(),
        ):
            bill.l10n_co_edi_action_send_bill_support_document()

        self.assertTrue(bill.l10n_co_edi_attachment_id)
        self.assertRecordValues(bill.l10n_co_edi_document_ids, [{
            'zip_key': False,
            'state': 'invoice_accepted',
            'message': "<p>Procesado Correctamente.</p>"
                       "<ul><li>Regla: FAJ44b, Notificación: Nit o Documento de Identificación informado No BlaBlaBla.</li>"
                       "<li>Regla: FAJ43b, Notificación: Nombre informado No corresponde al registrado en el BlaBlaBla.</li></ul>",
        }])

    def test_get_acquirer(self):
        """ Get Partner Data """
        partner = self._create_partner(
            country_id=self.env.ref('base.co').id,
            vat='213123432-1',
            email='test@mail.com',
        )

        with patch(f'{self.utils_path}._build_and_send_request', return_value=self._mocked_response('GetAcquirer_partner.xml', 200)):
            partner.button_l10n_co_edi_refresh_data()

        self.assertTrue(partner.child_ids)
        self.assertRecordValues(partner.child_ids[0], [{
            'name': 'Real Company Name',
            'email': 'company@mail.com',
        }])

    def test_get_aquirer_constraints(self):
        """Refresh is rejected on a child contact and on a partner that already has an invoicing child."""
        partner = self._create_partner(
            country_id=self.env.ref('base.co').id,
            vat='213123432-1',
            email='test@mail.com',
        )

        self.env['res.partner'].create({
            'name': 'Child Contact',
            'parent_id': partner.id,
            'type': 'invoice',
            'email': 'existing@mail.com',
        })
        with patch(f'{self.utils_path}._build_and_send_request', return_value=self._mocked_response('GetAcquirer_partner.xml', 200)):
            with self.assertRaisesRegex(UserError, "This contact has already been updated with DIAN information"):
                partner.button_l10n_co_edi_refresh_data()

    def test_invoice_date_constraints_dian(self):
        """Test that invoices date older than 6 days or more than 6 days ahead trigger the constraint."""
        bogota_today = fields.Date.context_today(self.env.user.with_context(tz='America/Bogota'))

        valid_invoice = self._create_move(invoice_date=bogota_today - timedelta(days=6))
        self._mock_send_and_print(move=valid_invoice, response_file='SendBillSync_warnings.xml')

        invalid_invoice = self._create_move(invoice_date=bogota_today - timedelta(days=7))
        with self.assertRaisesRegex(UserError, "The issue date can not be older than 6 days or more than 6 days in the future."):
            self._mock_send_and_print(move=invalid_invoice, response_file='SendBillSync_warnings.xml')

    def test_dian_state_machine(self):
        """
        Test how move.l10n_co_edi_state and move.l10n_co_edi_commercial_state change when
        communicating with DIAN.
        Communication with DIAN is always represented by a l10n_co_edi.document, which in turn
        could alter the states of the account.move.
        The tested sequence is as follows:
        1. sending failure because of a 500 response
        2. invoice rejected by dian
        3. invoice accepted by dian
        4. status updated with a response GetStatusEvent_no_events
        """
        # we are not testing for the UseError in this scope, so we ignore it.
        with contextlib.suppress(UserError):
            self._mock_send_and_print(self.invoice, 'unknown_error.xml', response_code=500)
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_sending_failed')
        self.assertFalse(self.invoice.l10n_co_edi_commercial_state)

        # we are not testing for the UseError in this scope, so we ignore it.
        with contextlib.suppress(UserError):
            self._mock_send_and_print(self.invoice, 'SendBillSync_errors.xml')
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_rejected')
        self.assertFalse(self.invoice.l10n_co_edi_commercial_state)

        self._mock_send_and_print(self.invoice, 'SendBillSync_warnings.xml')
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_accepted')
        self.assertEqual(self.invoice.l10n_co_edi_commercial_state, 'pending')

        track_id = self.invoice.l10n_co_edi_cufe_cude_ref
        with self._mock_build_and_send_request('GetStatusEvent_no_events.xml'):
            self.env['l10n_co_edi.document']._send_get_status_event(self.invoice, track_id)

        docs = self.invoice.l10n_co_edi_document_ids.sorted()
        self.assertEqual(docs[0].state, 'invoice_rejected')
        self.assertEqual(docs[1].state, 'invoice_accepted')
        self.assertEqual(self.invoice.l10n_co_edi_state, 'invoice_accepted')


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDianFlowsSettings(TestCoEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['res.config.settings'].create({})
        cls.settings.l10n_co_edi_test_environment = True
        cls.settings.l10n_co_edi_certification_process = True
        cls.settings.l10n_co_edi_cert_invoice_count = 2
        cls.settings.l10n_co_edi_cert_credit_count = 2
        cls.settings.l10n_co_edi_cert_debit_count = 2

    def _mocked_build_and_send_request(self, record, payload, service, company):
        """Build_and_send_request is a module level function in xml_util that contains a parameter
        self. To be able to mock it from within the test class we need an additional parameter to
        make sure it can be called."""
        if service == 'SendTestSetAsync':
            return self._mocked_response('SendTestSetAsync.xml', 200)
        if service == 'GetStatusZip':
            return self._mocked_response('GetStatusZip_habilitation.xml', 200)
        return self._mocked_response('', 200)

    def test_certification_process(self):
        """ Test the certification process with the DIAN. """
        with (
            patch(f'{self.utils_path}._build_and_send_request', autospec=True, side_effect=self._mocked_build_and_send_request),
            self._disable_get_acquirer_call(),
        ):
            self.settings.action_l10n_co_certify_with_dian()
        # Check that the journals were created or updated.
        journals = self.env['account.journal'].search([('code', 'in', ['SETP', 'NC', 'ND'])])
        self.assertEqual(len(journals), 3)

        # Unique journal values
        self.assertRecordValues(journals, [
            {'code': 'SETP', 'l10n_co_edi_min_range_number': 990000000, 'l10n_co_edi_max_range_number': 995000000, 'l10n_co_edi_debit_note': False},
            {'code': 'NC', 'l10n_co_edi_min_range_number': 1, 'l10n_co_edi_max_range_number': 1000, 'l10n_co_edi_debit_note': False},
            {'code': 'ND', 'l10n_co_edi_min_range_number': 1, 'l10n_co_edi_max_range_number': 1000, 'l10n_co_edi_debit_note': True},
        ])

        # Shared journal values
        self.assertRecordValues(journals, [{
            'l10n_co_edi_technical_key': 'fc8eac422eba16e22ffd8c6f94b3f40a6e38162c',
            'l10n_co_edi_dian_authorization_date': fields.Date.from_string('2019-01-19'),
            'l10n_co_edi_dian_authorization_end_date': fields.Date.from_string('2030-01-19'),
            'l10n_co_edi_dian_authorization_number': '18760000001',
        }] * 3)

        # Check that the moves were created
        moves = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('journal_id', 'in', journals.ids),
        ])
        self.assertEqual(len(moves), 6)

        # The test file we use is one already accepted so it should all be marked as already accepted.
        for move in moves:
            self.assertRecordValues(move.l10n_co_edi_document_ids, [{
                'zip_key': '42424242',
                'state': 'invoice_rejected',
                'message': "<p>Set de prueba con identificador 123456 se encuentra Aceptado.</p>",
            }])
