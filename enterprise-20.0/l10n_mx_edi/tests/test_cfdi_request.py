import requests

from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_cfdi_request import (
    SAT_MAX_DOWNLOAD_WAIT_DAYS,
    SAT_MAX_PROCESS_WAIT_DAYS,
    SAT_MAX_UNPACK_WAIT_DAYS,
)
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_sat_client import SAT_REQUEST_CODE_MAP
from odoo.addons.l10n_mx_edi.tests.common_sat_download import (
    TestCfdiRequestCommon,
    DEFAULT_CFDI_UUID,
    DEFAULT_REQUEST_UUID,
)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCfdiRequest(TestCfdiRequestCommon):

    def _request_vals(self, **kwargs):
        mx_today = self._mx_today()
        return {
            'company_id': self.env.company.id,
            'request_type': 'batch_issued',
            'receipt_type': 'I',
            'emission_date_from': mx_today - timedelta(days=31),
            'emission_date_to': mx_today - timedelta(days=1),
            **kwargs,
        }

    # -------------------------------------------------------------------------
    # Send
    # -------------------------------------------------------------------------

    def test_check_request_values(self):
        """Assert situations when request values are not valid."""
        mx_today = self._mx_today()
        cases = [
            ('folio without a fiscal folio', {'request_type': 'folio', 'cfdi_uuid': False}, False),
            ('missing end date', {'emission_date_to': False}, False),
            (
                'inverted range',
                {'emission_date_from': mx_today - timedelta(days=2), 'emission_date_to': mx_today - timedelta(days=3)},
                False,
            ),
            ("end date isn't settled yet", {'emission_date_to': mx_today}, False),
            # The default window starts 31 days back, well inside this lock.
            ('range starts inside a locked period', {}, mx_today - timedelta(days=5)),
        ]

        # No mock entries, so any call to SAT raises StopIteration instead of going out.
        with self.mocked_cfdi_requests([]):
            for scenario, vals, lock_date in cases:
                with self.subTest(scenario=scenario):
                    self.env.company.fiscalyear_lock_date = lock_date
                    with self.assertRaises(UserError):
                        self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(self._request_vals(**vals))

        self.assertFalse(self.env['l10n_mx_edi.cfdi.request'].search_count([]))

    def test_send_without_certificate(self):
        """Assert raises when no fiel certificate."""
        with self.mocked_cfdi_requests([]):
            with self.assertRaisesRegex(UserError, 'Not a valid FIEL'):
                self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(self._request_vals())

    def test_send_request(self):
        """Assert case for a succesful request sent."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            vals = self._request_vals()

            with self.subTest(case='SAT accepts'):
                with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='batch_issued')):
                    cfdi_request = self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(vals)
                self.assertRecordValues(cfdi_request, [{
                    'state': 'in_process_at_sat',
                    'request_uuid': DEFAULT_REQUEST_UUID,
                    'is_retryable': True,
                }])

            with self.subTest(case='SAT never answers'):
                with self.mocked_failed_cfdi_request(
                    error=requests.exceptions.ConnectionError('SAT is unreachable'),
                ):
                    with self.assertRaises(UserError):
                        self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(vals)
                # Still only the accepted one.
                self.assertEqual(self.env['l10n_mx_edi.cfdi.request'].search_count([]), 1)

    def test_sat_reject_errors(self):
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            vals = self._request_vals()
            for status_code in SAT_REQUEST_CODE_MAP:
                with self.subTest(status_code=status_code):
                    with self.mocked_send_cfdi_request(
                        self._build_request_download_response(status_code=status_code),
                    ):
                        cfdi_request = self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(vals)

                    # A settled state keeps it out of the crons; the flag is not needed for that.
                    self.assertRecordValues(cfdi_request, [{'state': 'rejected'}])
                    self.assertTrue(cfdi_request.message)

    def test_request_authentication(self):
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            vals = self._request_vals()
            with self.mocked_send_cfdi_request(
                self._build_request_download_response(request_type='batch_issued'),
                auth_response=self._build_auth_response('new-sat-token'),
            ):
                cfdi_request = self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(vals)

        self.assertEqual(cfdi_request.state, 'in_process_at_sat')
        self.assertEqual(self.fiel_certificate.sudo().l10n_mx_edi_sat_token, 'new-sat-token')

    def test_request_authentication_failure(self):
        """A step raises: nothing between it and whoever asked for it, so a button shows the error."""
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request()
            with self.mocked_cfdi_requests([{'auth_response': self._build_auth_response()}]):
                with self.assertRaisesRegex(UserError, 'Failed to renew Token'):
                    cfdi_request.action_verify_request()

        self.assertFalse(self.fiel_certificate.sudo().l10n_mx_edi_sat_token)
        self.assertRecordValues(cfdi_request, [{'state': 'in_process_at_sat', 'is_retryable': True}])

    def test_retry_request(self):
        """Retrying a request creates a new request."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            rejected = self._create_new_request(state='rejected', is_retryable=False)
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='batch_issued')):
                action = rejected.action_retry_request()
        new_request_id = action and action['res_id']
        new_request = self.env['l10n_mx_edi.cfdi.request'].browse(new_request_id)
        self.assertNotEqual(new_request, rejected)
        self.assertRecordValues(new_request + rejected, [
            {'state': 'in_process_at_sat', 'request_uuid': DEFAULT_REQUEST_UUID, 'is_retryable': True},
            {'state': 'rejected', 'request_uuid': False, 'is_retryable': False},
        ])
        self.assertRecordValues(new_request, [{
            'request_type': rejected.request_type,
            'receipt_type': rejected.receipt_type,
            'emission_date_from': rejected.emission_date_from,
            'emission_date_to': rejected.emission_date_to,
        }])

    def test_cron_process_only_due_requests(self):
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            due = self._create_new_request()
            blocked = self._create_new_request(is_retryable=False)
            done = self._create_new_request(state='done')

            with self.mocked_cfdi_requests([{'response': self._build_verification_response(request_status=2)}]):
                self._trigger_cron(self.verify_cron)

        self.assertRegex(due.message, 'Request is still in process. Try later')
        self.assertRecordValues(blocked + done, [
            {'state': 'in_process_at_sat', 'is_retryable': False, 'message': False},
            {'state': 'done', 'is_retryable': True, 'message': False},
        ])

    def test_cron_request_not_processed_twice(self):
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            self.verify_cron.code = 'model._cron_verify_requests(batch_size=1)'
            requests_to_verify = [self._create_new_request() for _ in range(2)]

            with self.mocked_cfdi_requests([
                {'response': self._build_verification_response(request_status=2)} for _ in range(2)
            ]):
                self._trigger_cron(self.verify_cron)

        for cfdi_request in requests_to_verify:
            self.assertEqual(cfdi_request.last_cron_attempt, self.frozen_today)
            self.assertRegex(cfdi_request.message, 'Request is still in process. Try later')

    def test_cron_request_processed_on_next_call(self):
        still_in_process = [{'response': self._build_verification_response(request_status=2)}]
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request()
            with self.mocked_cfdi_requests(still_in_process):
                self._trigger_cron(self.verify_cron)
            self.assertEqual(cfdi_request.last_cron_attempt, self.frozen_today)

        next_run = self.frozen_today + timedelta(hours=1)
        with self.mx_frozen_now(next_run, certificate=self.fiel_certificate):
            with self.mocked_cfdi_requests(still_in_process):
                self._trigger_cron(self.verify_cron)

        self.assertEqual(cfdi_request.last_cron_attempt, next_run)

    def test_cron_continues_after_a_request_fails(self):
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            failed = self._create_new_request()
            following = self._create_new_request()

            with self.mocked_cfdi_requests([
                {'error': requests.exceptions.ConnectionError('SAT is unreachable')},
                {'response': self._build_verification_response()},
            ]):
                self._trigger_cron(self.verify_cron)

        self.assertRecordValues(failed + following, [
            {'state': 'in_process_at_sat', 'is_retryable': True},
            {'state': 'in_download', 'is_retryable': True},
        ])

    def test_cron_skips_a_locked_request(self):
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request()
            with patch.object(
                self.env.registry['l10n_mx_edi.cfdi.request'], 'try_lock_for_update',
                lambda records, **kwargs: records.browse(),
            ), self.mocked_cfdi_requests([]):
                self._trigger_cron(self.verify_cron)

        self.assertRecordValues(cfdi_request, [{
            'state': 'in_process_at_sat',
            'is_retryable': True,
            'message': False,
            'last_cron_attempt': False,
        }])

    def test_cron_blocks_stale_requests(self):
        def build_in_process():
            return self._create_new_request()

        def build_in_download():
            return self._create_new_request(state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_01')

        def build_unpacking():
            request = self._create_new_request(state='unpacking')
            request.attachment_id = self._create_request_attachment(self.default_cfdi_package_raw, request)
            return request

        for state, max_wait_days, build_request, cron in (
            ('in_process_at_sat', SAT_MAX_PROCESS_WAIT_DAYS, build_in_process, self.verify_cron),
            ('in_download', SAT_MAX_DOWNLOAD_WAIT_DAYS, build_in_download, self.download_cron),
            ('unpacking', SAT_MAX_UNPACK_WAIT_DAYS, build_unpacking, self.unpack_cron),
        ):
            with self.subTest(state=state):
                frozen_today = self.frozen_today - timedelta(days=max_wait_days, seconds=1)
                with self.mx_frozen_now(frozen_today, certificate=self.fiel_certificate):
                    cfdi_request = build_request()

                with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
                    with self.mocked_cfdi_requests([]), self.enter_registry_test_mode():
                        cron.method_direct_trigger()

                self.assertRecordValues(cfdi_request, [{'state': state, 'is_retryable': False}])
                self.assertTrue(cfdi_request.message)

    def test_sat_request_errors(self):
        cases = [
            ('SAT unreachable', {'error': requests.exceptions.ConnectionError('down')}),
            ('server error', {'http_status': 500}),
            ('bad credentials', {'http_status': 401}),
            ('certificate revoked', {'response': self._build_verification_response(status_code='304')}),
            ('unprocessed through CodEstatus', {'response': self._build_verification_response(
                status_code=None, code_status='305',
            )}),
        ]
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            for scenario, sat_answer in cases:
                with self.subTest(scenario=scenario):
                    cfdi_request = self._create_new_request()
                    # The step raises rather than recording: only the cron turns this into a message.
                    with self.mocked_cfdi_requests([sat_answer]):
                        with self.assertRaises(UserError):
                            cfdi_request._verify_request()

                    self.assertRecordValues(cfdi_request, [{
                        'state': 'in_process_at_sat',
                        'is_retryable': True,
                    }])

    def test_verification_status_codes(self):
        cases = [
            ('still queued', {'request_status': 1}, 'in_process_at_sat'),
            ('in process', {'request_status': 2}, 'in_process_at_sat'),
            ('SAT-side error', {'request_status': 4}, 'in_process_at_sat'),
            ('rejected', {'request_status': 5, 'status_code': '5003'}, 'rejected'),
            ('expired', {'request_status': 6}, 'expired'),
            ('ready', {'n_uuids': 1}, 'in_download'),
            ('nothing found', {'n_uuids': 0}, 'done'),
            ('unknown status', {'request_status': 99}, 'in_process_at_sat'),
        ]
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request()
            for scenario, response_kwargs, expected_state in cases:
                with self.subTest(scenario=scenario):
                    cfdi_request.write({'state': 'in_process_at_sat', 'is_retryable': True})
                    with self.mocked_cfdi_requests([
                        {'response': self._build_verification_response(**response_kwargs)},
                    ]):
                        cfdi_request._verify_request()

                    self.assertRecordValues(cfdi_request, [{'state': expected_state}])

    def test_request_success_step_clears_attempt(self):
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request(
                last_cron_attempt=self.frozen_today, is_retryable=False,
            )
            with self.mocked_cfdi_requests([{'response': self._build_verification_response()}]):
                cfdi_request.action_verify_request()

        self.assertRecordValues(cfdi_request, [{
            'state': 'in_download',
            'ready_at': self.frozen_today,
            'last_cron_attempt': False,
            'is_retryable': True,
        }])

    def test_request_split_into_several_packages(self):
        """SAT splits a large result into several packages, each downloaded on its own."""
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request()
            with self.mocked_cfdi_requests([{'response': self._build_verification_response(n_uuids=5)}]):
                cfdi_request._verify_request()

        packages = self.env['l10n_mx_edi.cfdi.request'].search(
            [('request_uuid', '=', cfdi_request.request_uuid)], order='package_uuid',
        )
        self.assertEqual(len(packages), 5)
        self.assertEqual(set(packages.mapped('state')), {'in_download'})
        self.assertEqual(
            packages.mapped('package_uuid'),
            [f'{DEFAULT_REQUEST_UUID}_{i + 1:02d}' for i in range(5)],
        )

    def test_request_unpacking_after_download(self):
        """Assert that a request after completing download step, next step is to unpackage."""
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request(
                state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_01',
            )
            with self.mocked_cfdi_requests([
                {'response': self._build_package_download_response(package_zip=self.default_cfdi_package_raw)},
            ]):
                cfdi_request._download_package()

            self.assertRecordValues(cfdi_request, [{'state': 'unpacking', 'unpacked_count': 0}])
            self.assertEqual(cfdi_request.attachment_id.raw.content, self.default_cfdi_package_raw)
            self.assertFalse(cfdi_request.l10n_mx_edi_document_ids)

            cfdi_request._unpack_package_batch()

        self.assertRecordValues(cfdi_request, [{'state': 'done', 'unpacked_count': 1}])
        documents = cfdi_request.l10n_mx_edi_document_ids
        self.assertEqual(set(documents.mapped('state')), {'to_import'})
        self.assertEqual(
            self.env['l10n_mx_edi.document'].search(cfdi_request.action_open_documents()['domain']),
            documents,
        )

    def test_request_unpacking_in_batches(self):
        """Assert that unpacking a request response is done in batches without replicating."""
        uuids = [f'{DEFAULT_CFDI_UUID[:-2]}{i:02d}' for i in range(5)]
        package_raw = self._create_sat_package_zip(data=[(uuid, 'I') for uuid in uuids])

        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            cfdi_request = self._create_new_request(
                state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_01',
            )
            with self.mocked_cfdi_requests([
                {'response': self._build_package_download_response(package_zip=package_raw)},
            ]):
                cfdi_request._download_package()

            self.assertEqual(cfdi_request.state, 'unpacking')
            for expected_count in (2, 4, 5):
                cfdi_request._unpack_package_batch(batch_size=2)
                self.assertEqual(cfdi_request.unpacked_count, expected_count)

        self.assertEqual(cfdi_request.state, 'done')
        self.assertEqual(sorted(cfdi_request.l10n_mx_edi_document_ids.mapped('attachment_uuid')), sorted(uuids))

    def test_unpacking_duplicate_cfdi_skips(self):
        """If a package contains already existing cfdi, those are skipped and package marked as done anyways."""
        package_raw = self._create_sat_package_zip(data=[(DEFAULT_CFDI_UUID, 'I')])
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            first = self._create_new_request(state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_01')
            second = self._create_new_request(state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_02')
            for cfdi_request in (first, second):
                with self.mocked_cfdi_requests([
                    {'response': self._build_package_download_response(package_zip=package_raw)},
                ]):
                    cfdi_request._download_package()
                cfdi_request._unpack_package_batch()

        self.assertRecordValues(first + second, [
            {'state': 'done', 'unpacked_count': 1},
            {'state': 'done', 'unpacked_count': 1},
        ])
        self.assertTrue(first.l10n_mx_edi_document_ids)
        self.assertFalse(second.l10n_mx_edi_document_ids)

    def test_unusable_package_blocks(self):
        cases = [
            ('empty', None),
            ('not a zip', b'PK\x03\x04 truncated, not a real zip'),
        ]
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            for scenario, package_zip in cases:
                with self.subTest(scenario=scenario):
                    cfdi_request = self._create_new_request(
                        state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_01',
                    )
                    with self.mocked_cfdi_requests([
                        {'response': self._build_package_download_response(package_zip=package_zip)},
                    ]):
                        cfdi_request._download_package()

                    self.assertRecordValues(cfdi_request, [{
                        'state': 'in_download',
                        'is_retryable': False,
                    }])
                    self.assertFalse(cfdi_request.attachment_id)
                    self.assertFalse(cfdi_request.l10n_mx_edi_document_ids)

    def test_package_download_sat_codes(self):
        cases = [
            ('5004', 'rejected'),  # SAT lost the package it handed us, or it was empty.
            ('5007', 'expired'),
            ('5008', 'rejected'),
        ]
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            for status_code, expected_state in cases:
                with self.subTest(status_code=status_code):
                    cfdi_request = self._create_new_request(
                        state='in_download', package_uuid=f'{DEFAULT_REQUEST_UUID}_01',
                    )
                    with self.mocked_cfdi_requests([
                        {'response': self._build_package_download_response(status_code=status_code)},
                    ]):
                        cfdi_request._download_package()

                    self.assertRecordValues(cfdi_request, [{'state': expected_state}])

    def test_batch_request_full_flow(self):
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            vals = self._request_vals()
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='batch_issued')):
                cfdi_request = self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(vals)
            self.assertRecordValues(cfdi_request, [{'state': 'in_process_at_sat', 'request_uuid': DEFAULT_REQUEST_UUID}])

            with self.mocked_cfdi_requests([
                {'response': self._build_verification_response()},
                {'response': self._build_package_download_response(package_zip=self.default_cfdi_package_raw)},
            ]), self.enter_registry_test_mode():
                self.verify_cron.method_direct_trigger()
                self.assertEqual(cfdi_request.state, 'in_download')
                self.download_cron.method_direct_trigger()
                self.assertEqual(cfdi_request.state, 'unpacking')
                self.assertEqual(cfdi_request.attachment_id.raw.content, self.default_cfdi_package_raw)
                self.unpack_cron.method_direct_trigger()
                self.assertFalse(cfdi_request.attachment_id, "Package ZIP should be deleted")

            self.assertRecordValues(cfdi_request, [{
                'state': 'done',
                'package_uuid': f'{DEFAULT_REQUEST_UUID}_01',
                'unpacked_count': 1,
                'is_retryable': True,
            }])
            for cron in (self.verify_cron, self.download_cron, self.unpack_cron):
                self.assertFalse(self.env['ir.cron.trigger'].search_count([('cron_id', '=', cron.id)]))

        documents = cfdi_request.l10n_mx_edi_document_ids
        self.assertTrue(documents)
        self.assertEqual(set(documents.mapped('state')), {'to_import'})

    def test_folio_request_full_flow(self):
        with self.mx_frozen_now(self.frozen_today, certificate=self.fiel_certificate):
            vals = self._request_vals(request_type='folio', cfdi_uuid=DEFAULT_CFDI_UUID)
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='folio')):
                cfdi_request = self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(vals)
            self.assertRecordValues(cfdi_request, [{
                'state': 'in_process_at_sat',
                'cfdi_uuid': DEFAULT_CFDI_UUID,
                'request_uuid': DEFAULT_REQUEST_UUID,
            }])

            with self.mocked_cfdi_requests([{'response': self._build_verification_response()}]):
                cfdi_request._verify_request()
            self.assertEqual(cfdi_request.state, 'in_download')

            with self.mocked_cfdi_requests([
                {'response': self._build_package_download_response(package_zip=self.default_cfdi_package_raw)},
            ]):
                cfdi_request._download_package()
            self.assertEqual(cfdi_request.state, 'unpacking')

            cfdi_request._unpack_package_batch()

        self.assertEqual(cfdi_request.state, 'done')
        self.assertEqual(set(cfdi_request.l10n_mx_edi_document_ids.mapped('state')), {'to_import'})
