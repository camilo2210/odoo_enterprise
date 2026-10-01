from odoo.tests import tagged
from .common import TestPeEdiCommon, CODE_98_ERROR_MSG, MAX_WAIT_ITER, _get_pe_current_datetime

from datetime import timedelta
from time import sleep
from freezegun import freeze_time


@tagged('external_l10n', 'post_install', '-at_install', '-standard', 'external')
class TestEdiDigiflow(TestPeEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].l10n_pe_edi_provider = 'digiflow'

    def test_10_invoice_edi_flow(self):
        yesterday = _get_pe_current_datetime().date() - timedelta(1)
        move = self._create_invoice_pe(invoice_date=yesterday, date=yesterday)
        move.action_post()

        # Send
        move._l10n_pe_edi_post_invoice()
        self.assertRecordValues(move, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 1
        move.l10n_pe_edi_cancel_reason = 'abc'
        self.assertFalse(move.l10n_pe_edi_cancel_cdr_number)
        move.button_request_cancel()
        self.assertTrue(move.l10n_pe_edi_cancel_cdr_number)
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 2
        # We need to wait a bit before requesting the cancellation's status
        # to avoid getting a status code 98 (cancellation still being processed).
        for _ in range(MAX_WAIT_ITER):
            sleep(10)
            move.button_request_cancel()
            if not move.l10n_pe_edi_warnings or move.l10n_pe_edi_warnings['edi_error']['message'] != CODE_98_ERROR_MSG:
                break

        self.assertRecordValues(move, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'cancelled'}])

    def test_20_refund_edi_flow(self):
        today = _get_pe_current_datetime().date()
        move = self._create_refund(invoice_date=today, date=today)
        (move.reversed_entry_id + move).action_post()

        # Send
        move.reversed_entry_id._l10n_pe_edi_post_invoice()
        move._l10n_pe_edi_post_invoice()
        self.assertRecordValues(move, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move.reversed_entry_id, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])
        self.assertRecordValues(move.reversed_entry_id, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 1
        move.l10n_pe_edi_cancel_reason = 'abc'
        self.assertFalse(move.l10n_pe_edi_cancel_cdr_number)
        move.button_request_cancel()
        self.assertTrue(move.l10n_pe_edi_cancel_cdr_number)
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])
        self.assertRecordValues(move.reversed_entry_id, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 2
        # We need to wait a bit before requesting the cancellation's status
        # to avoid getting a status code 98 (cancellation still being processed).
        for _ in range(MAX_WAIT_ITER):
            sleep(10)
            move.button_request_cancel()
            if not move.l10n_pe_edi_warnings or move.l10n_pe_edi_warnings['edi_error']['message'] != CODE_98_ERROR_MSG:
                break

        self.assertRecordValues(move, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'cancelled'}])

    def test_30_debit_note_edi_flow(self):
        today = _get_pe_current_datetime().date()
        move = self._create_debit_note(invoice_date=today, date=today)
        (move.debit_origin_id + move).action_post()

        # Send
        move.debit_origin_id._l10n_pe_edi_post_invoice()
        move._l10n_pe_edi_post_invoice()
        self.assertRecordValues(move, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move.debit_origin_id, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])
        self.assertRecordValues(move.debit_origin_id, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 1
        move.l10n_pe_edi_cancel_reason = 'abc'
        self.assertFalse(move.l10n_pe_edi_cancel_cdr_number)
        move.button_request_cancel()
        self.assertTrue(move.l10n_pe_edi_cancel_cdr_number)
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])
        self.assertRecordValues(move.debit_origin_id, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 2
        # We need to wait a bit before requesting the cancellation's status
        # to avoid getting a status code 98 (cancellation still being processed).
        for _ in range(MAX_WAIT_ITER):
            sleep(10)
            move.button_request_cancel()
            if not move.l10n_pe_edi_warnings or move.l10n_pe_edi_warnings['edi_error']['message'] != CODE_98_ERROR_MSG:
                break

        self.assertRecordValues(move, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'cancelled'}])
        self.assertRecordValues(move.debit_origin_id, [{'l10n_pe_edi_status': 'cancelled'}])

    @freeze_time("2025-11-30 12:00:00")
    def test_40_catch_error_in_cdr_cancel(self):
        """
        Check that we correctly detect errors reported in the ResponseCode field of the CDR
        when cancelling an invoice.
        The error in this is that we can only cancel records created within the last few days. So
        freezetime causes the cancellation to always fail.
        """
        today = _get_pe_current_datetime().date()
        yesterday = today - timedelta(1)
        move = self._create_invoice_pe(invoice_date=yesterday, date=yesterday, name='F FFI-%s4' % self.time_name)
        move.action_post()

        move._l10n_pe_edi_post_invoice()
        self.assertRecordValues(move, [{'l10n_pe_edi_warnings': False}])
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 1
        move.l10n_pe_edi_cancel_reason = 'abc'
        self.assertFalse(move.l10n_pe_edi_cancel_cdr_number)
        move.button_request_cancel()
        expected_error = "We got an error response from the OSE.\n*Original message:*\n2957|El comprobante no puede ser dado de baja por exceder el plazo desde su fecha de emision"
        actual_error = move.l10n_pe_edi_warnings['edi_error']['message']
        self.assertTrue(actual_error.startswith(expected_error), f'Error response: {actual_error}')
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])
        self.assertTrue(move.l10n_pe_edi_cancel_cdr_number)
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])

        # Cancel step 2
        # We need to wait a bit before requesting the cancellation's status
        # to avoid getting a status code 98 (cancellation still being processed).
        for _ in range(MAX_WAIT_ITER):
            sleep(10)
            move.button_request_cancel()
            if not move.l10n_pe_edi_warnings or move.l10n_pe_edi_warnings['edi_error']['message'] != CODE_98_ERROR_MSG:
                break

        expected_error = "We got an error response from the OSE.\n*Original message:*\n2957|El comprobante no puede ser dado de baja por exceder el plazo desde su fecha de emision"
        actual_error = move.l10n_pe_edi_warnings['edi_error']['message']
        self.assertTrue(actual_error.startswith(expected_error), f'Error response: {actual_error}')
        self.assertRecordValues(move, [{'l10n_pe_edi_status': 'sent'}])
