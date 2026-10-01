from unittest.mock import patch

from odoo.tests import tagged
from .common import TestPeEdiCommon

VALID_CDR = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<ar:ApplicationResponse
    xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ResponseCode>0</cbc:ResponseCode>
    <cbc:Description>The invoice has been accepted</cbc:Description>
</ar:ApplicationResponse>
"""

INVALID_CDR = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<ar:ApplicationResponse
    xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ResponseCode>2800</cbc:ResponseCode>
    <cbc:Description>The invoice has been rejected</cbc:Description>
</ar:ApplicationResponse>
"""


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestEdiRetrieveCdr(TestPeEdiCommon):
    """ Check that _l10n_pe_edi_retrieve_cdr() only marks a result retryable ('retry': True) when
    we don't have a definitive answer from SUNAT yet, and leaves it non-retryable once SUNAT has
    definitively rejected the document, so the send cron doesn't retry forever on a lost cause. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.move = cls._create_invoice_pe(cls)

    def _retrieve_cdr(self, get_status_cdr_return_value):
        with patch(
            'odoo.addons.l10n_pe_edi.models.account_move.AccountMove._l10n_pe_edi_get_status_cdr_sunat_estela',
            return_value=get_status_cdr_return_value,
        ):
            return self.move._l10n_pe_edi_retrieve_cdr()

    def test_transient_connection_error_is_retried(self):
        """ The underlying service couldn't even reach SUNAT (e.g. timeout): worth retrying. """
        res = self._retrieve_cdr({'message': 'connection timed out', 'retry': True})
        self.assertTrue(res['retry'])

    def test_cdr_not_yet_available_is_retried(self):
        """ SUNAT answered but the CDR isn't generated yet: still worth retrying. """
        res = self._retrieve_cdr({'message': 'CDR not found yet', 'retry': True})
        self.assertTrue(res['retry'])

    def test_soap_fault_without_retry_flag_is_not_retried(self):
        """ A genuine SOAP fault from SUNAT with no explicit 'retry' must not be silently
        treated as retryable. """
        res = self._retrieve_cdr({'message': 'invalid VAT number', 'code': '1034'})
        self.assertFalse(res.get('retry'))

    def test_soap_fault_marked_not_retryable_stays_not_retryable(self):
        res = self._retrieve_cdr({'message': 'invalid VAT number', 'retry': False, 'code': '1034'})
        self.assertFalse(res.get('retry'))

    def test_unexpected_status_code_is_retried(self):
        """ A response without a 'message' but whose status code isn't the expected 0004
        ('CDR exists') is treated as inconclusive, not a definitive rejection. """
        res = self._retrieve_cdr({'code': '0001', 'status': '0001|In progress'})
        self.assertTrue(res['retry'])

    def test_cdr_retrieved_and_valid(self):
        res = self._retrieve_cdr({'code': '0004', 'cdr': VALID_CDR})
        self.assertFalse(res.get('message'))

    def test_cdr_retrieved_but_invalid_is_not_retried(self):
        """ SUNAT's own CDR says the document is invalid: retrying will never change that answer,
        so this must not be retried by the send cron forever. """
        res = self._retrieve_cdr({'code': '0004', 'cdr': INVALID_CDR})
        self.assertFalse(res.get('retry'))
