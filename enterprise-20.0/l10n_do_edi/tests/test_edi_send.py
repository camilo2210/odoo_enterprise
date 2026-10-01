from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import freeze_time
from .common import TestDoEdiCommon
from .mock_response import (
    PATCH_GET_TARGET,
    PATCH_POST_TARGET,
    PATCH_SEND_SESSION_TARGET,
    mock_dgii_accepted_response,
    mock_dgii_rejected_response,
    mock_ecf_rejected_response,
    mock_ecf_success_response,
    mock_login_response,
    mock_signed_xml_response,
)


@tagged('post_install_l10n', 'post_install', '-at_install')
@freeze_time('2026-01-15')
class TestEdiSend(TestDoEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({
            'l10n_do_edi_web_service_env': 'test',
            'l10n_do_edi_username': 'test_user',
            'l10n_do_edi_password': 'test_password',
            'l10n_do_edi_key': 'test_key',
            'l10n_do_edi_llave': 'test_llave',
        })

    def _get_send_wizard(self, invoice):
        return self.env['account.move.send.wizard']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({'sending_methods': []})

    def test_send_invoice_success(self):
        """ Test successful invoice sending to Infile """
        invoice = self._create_invoice()
        invoice.action_post()

        mock_session = MagicMock()
        mock_session.__enter__.return_value.post.side_effect = [mock_ecf_success_response(1)]
        with patch(PATCH_POST_TARGET, return_value=mock_login_response()), \
             patch(PATCH_GET_TARGET, return_value=mock_signed_xml_response()), \
             patch(PATCH_SEND_SESSION_TARGET, return_value=mock_session):
            wizard = self._get_send_wizard(invoice)
            wizard.action_send_and_print()

        self.assertEqual(invoice.l10n_do_edi_state, 'infile_accepted')
        self.assertEqual(invoice.l10n_do_edi_qr_url, 'https://dgii.gov.do/qr/test')
        self.assertEqual(invoice.l10n_do_edi_security_code, 'ABC123')
        self.assertTrue(invoice.l10n_do_edi_signature_datetime)

    def test_send_invoice_auth_failure(self):
        """ Test authentication failure with Infile """
        invoice = self._create_invoice()
        invoice.action_post()

        with self.assertRaises(UserError), \
             patch(PATCH_POST_TARGET, side_effect=requests.exceptions.ConnectionError('Connection refused')), \
             self.assertLogs('odoo.addons.l10n_do_edi.models.account_move', level='ERROR'):
            wizard = self._get_send_wizard(invoice)
            wizard.action_send_and_print()

    def test_send_invoice_rejected(self):
        """ Test invoice rejected by Infile """
        invoice = self._create_invoice()
        invoice.action_post()

        mock_session = MagicMock()
        mock_session.__enter__.return_value.post.side_effect = [mock_ecf_rejected_response()]
        with patch(PATCH_POST_TARGET, return_value=mock_login_response()), \
             patch(PATCH_SEND_SESSION_TARGET, return_value=mock_session):
            wizard = self._get_send_wizard(invoice)
            wizard.action_send_and_print()

        self.assertEqual(invoice.l10n_do_edi_state, 'infile_rejected')

    def test_request_dgii_status_accepted(self):
        """ Test requesting DGII status via button - accepted """
        invoice = self._create_invoice()
        invoice.action_post()
        invoice.write({
            'l10n_do_edi_state': 'infile_accepted',
            'l10n_do_edi_request_identifier': 'REQ-001',
        })

        with patch(PATCH_POST_TARGET, return_value=mock_login_response()), \
             patch(PATCH_GET_TARGET, return_value=mock_dgii_accepted_response()):
            invoice.action_l10n_do_edi_request_dgii_status()

        self.assertEqual(invoice.l10n_do_edi_state, 'dgii_accepted')

    def test_request_dgii_status_rejected(self):
        """ Test requesting DGII status via button - rejected """
        invoice = self._create_invoice()
        invoice.action_post()
        invoice.write({
            'l10n_do_edi_state': 'infile_accepted',
            'l10n_do_edi_request_identifier': 'REQ-001',
        })

        with patch(PATCH_POST_TARGET, return_value=mock_login_response()), \
             patch(PATCH_GET_TARGET, return_value=mock_dgii_rejected_response()):
            invoice.action_l10n_do_edi_request_dgii_status()

        self.assertEqual(invoice.l10n_do_edi_state, 'dgii_rejected')

    def test_send_invoice_demo_mode(self):
        """ Test that demo mode skips actual requests """
        self.company.l10n_do_edi_web_service_env = 'demo'

        invoice = self._create_invoice()
        invoice.action_post()

        wizard = self._get_send_wizard(invoice)
        wizard.action_send_and_print()

        self.assertEqual(invoice.l10n_do_edi_state, 'dgii_accepted')

    def test_send_batch_invoices_multi_company(self):
        """ Test sending invoices from different companies in a single batch """
        company_2_data = self.setup_other_company()
        company_2 = company_2_data['company']
        company_2.write({
            'vat': '088390123',
            'street': 'Calle Test 456',
            'l10n_do_edi_web_service_env': 'test',
            'l10n_do_edi_username': 'test_user_2',
            'l10n_do_edi_password': 'test_password_2',
            'l10n_do_edi_key': 'test_key_2',
            'l10n_do_edi_llave': 'test_llave_2',
        })

        journal_2 = company_2_data['default_journal_sale']
        journal_2.l10n_latam_use_documents = True

        tax_2 = company_2_data['default_tax_sale']
        tax_2.write({'amount': 18, 'l10n_do_edi_invoicing_indicator': '1'})

        # Set up document type range for company 2
        range_31_c2 = self.env['l10n_do_edi.document.type.range'].create({
            'start_number': 1,
            'end_number': 10000,
            'expiration_date': '2026-12-31',
            'company_id': company_2.id,
        })
        self.doc_type_31.with_company(company_2).l10n_do_edi_property_document_range_id = range_31_c2

        invoice_1 = self._create_invoice()
        invoice_2 = self._create_invoice(
            company_id=company_2.id,
            journal_id=journal_2.id,
            invoice_line_ids=[(0, 0, {
                'product_id': self.product_a.id,
                'price_unit': 1000.0,
                'quantity': 1,
                'tax_ids': [(6, 0, tax_2.ids)],
            })],
        )
        multi_company_invoices = invoice_1 + invoice_2
        multi_company_invoices.action_post()

        # 2 logins (one per company)
        post_responses = [mock_login_response(), mock_login_response()]
        # 2 signed xml downloads
        get_responses = [mock_signed_xml_response(), mock_signed_xml_response()]
        # 2 ecf sends via session (one per invoice)
        mock_session = MagicMock()
        mock_session.__enter__.return_value.post.side_effect = [
            mock_ecf_success_response(1), mock_ecf_success_response(2),
        ]

        with patch(PATCH_POST_TARGET, side_effect=post_responses), \
             patch(PATCH_GET_TARGET, side_effect=get_responses), \
             patch(PATCH_SEND_SESSION_TARGET, return_value=mock_session):
            self.env['account.move.send'] \
                .with_context(allowed_company_ids=[self.company.id, company_2.id]) \
                ._generate_and_send_invoices(multi_company_invoices)

        # invoice_1
        self.assertEqual(invoice_1.l10n_do_edi_state, 'infile_accepted')
        self.assertTrue(invoice_1.l10n_do_edi_signature_datetime)
        self.assertTrue(invoice_1.l10n_do_edi_security_code)
        self.assertTrue(invoice_1.l10n_do_edi_qr_url)
        self.assertTrue(invoice_1.l10n_do_edi_request_identifier)
        # invoice_2
        self.assertEqual(invoice_2.l10n_do_edi_state, 'infile_accepted')
        self.assertTrue(invoice_2.l10n_do_edi_signature_datetime)
        self.assertTrue(invoice_2.l10n_do_edi_security_code)
        self.assertTrue(invoice_2.l10n_do_edi_qr_url)
        self.assertTrue(invoice_2.l10n_do_edi_request_identifier)

    def test_send_batch_invoices_partial_error(self):
        """ Test batch sending where one invoice is rejected and the other succeeds.
        The rejected invoice should not block the successful one from being sent. """
        invoice_1 = self._create_invoice()
        invoice_2 = self._create_invoice()
        invoices = invoice_1 + invoice_2
        invoices.action_post()

        # 1 login (same company)
        # ecf sends via session: 1 rejected + 1 success
        mock_session = MagicMock()
        mock_session.__enter__.return_value.post.side_effect = [
            mock_ecf_rejected_response(), mock_ecf_success_response(2),
        ]
        get_responses = [mock_signed_xml_response()]

        with patch(PATCH_POST_TARGET, return_value=mock_login_response()), \
             patch(PATCH_GET_TARGET, side_effect=get_responses), \
             patch(PATCH_SEND_SESSION_TARGET, return_value=mock_session):
            self.env['account.move.send']._generate_and_send_invoices(invoices)

        # invoice_1 should be rejected
        self.assertEqual(invoice_1.l10n_do_edi_state, 'infile_rejected')
        self.assertFalse(invoice_1.l10n_do_edi_signature_datetime)
        self.assertFalse(invoice_1.l10n_do_edi_security_code)
        self.assertFalse(invoice_1.l10n_do_edi_qr_url)

        # invoice_2 should still succeed
        self.assertEqual(invoice_2.l10n_do_edi_state, 'infile_accepted')
        self.assertTrue(invoice_2.l10n_do_edi_signature_datetime)
        self.assertTrue(invoice_2.l10n_do_edi_security_code)
        self.assertTrue(invoice_2.l10n_do_edi_qr_url)
        self.assertTrue(invoice_2.l10n_do_edi_request_identifier)
