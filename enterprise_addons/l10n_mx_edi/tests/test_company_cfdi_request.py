from contextlib import closing
from datetime import date, timedelta
from unittest.mock import patch

import requests
from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.models.res_company import SAT_STAMP_LAG_DAYS
from odoo.addons.l10n_mx_edi.tests.common_sat_download import DEFAULT_REQUEST_UUID, TestCfdiRequestCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCompanyRequest(TestCfdiRequestCommon):

    def test_create_requests_first_time(self):
        """With no prior sync, the cron asks SAT for the last few days up to today."""
        company = self.env.company
        company.l10n_mx_edi_last_sync = False
        sat_accepts = {'response': self._build_request_download_response(request_type='batch_received')}

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            mx_today = self._mx_today()
            # The cron sends inline, one request per receipt type, so SAT answers twice.
            with self.mocked_cfdi_requests([sat_accepts, sat_accepts]):
                self._trigger_cron(self.company_cron)

        cfdi_requests = self.env['l10n_mx_edi.cfdi.request'].search(
            [('company_id', '=', company.id)], order='receipt_type',  # I, then E
        )
        real_mx_today = date(mx_today.year, mx_today.month, mx_today.day)
        self.assertRecordValues(cfdi_requests, [
            {
                'request_type': 'batch_received',
                'receipt_type': 'I',
                'state': 'in_process_at_sat',
                'request_uuid': DEFAULT_REQUEST_UUID,
                'emission_date_from': real_mx_today - timedelta(days=SAT_STAMP_LAG_DAYS),
                'emission_date_to': real_mx_today - timedelta(days=1),
            },
            {
                'request_type': 'batch_received',
                'receipt_type': 'E',
                'state': 'in_process_at_sat',
                'request_uuid': DEFAULT_REQUEST_UUID,
                'emission_date_from': real_mx_today - timedelta(days=SAT_STAMP_LAG_DAYS),
                'emission_date_to': real_mx_today - timedelta(days=1),
            },
        ])
        self.assertEqual(company.l10n_mx_edi_last_sync, mx_today)

    def test_create_requests_last_sync(self):
        """The date range runs from a few days before the last sync up to today."""
        company = self.env.company
        sat_accepts = {'response': self._build_request_download_response(request_type='batch_received')}

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            mx_today = self._mx_today()
            last_sync = mx_today - timedelta(days=10)
            company.l10n_mx_edi_last_sync = last_sync
            with self.mocked_cfdi_requests([sat_accepts, sat_accepts]):
                self._trigger_cron(self.company_cron)

        cfdi_requests = self.env['l10n_mx_edi.cfdi.request'].search([('company_id', '=', company.id)])
        self.assertRecordValues(cfdi_requests, [
            {
                'state': 'in_process_at_sat',
                'emission_date_from': last_sync - timedelta(days=SAT_STAMP_LAG_DAYS),
                'emission_date_to': mx_today - timedelta(days=1),
            },
            {
                'state': 'in_process_at_sat',
                'emission_date_from': last_sync - timedelta(days=SAT_STAMP_LAG_DAYS),
                'emission_date_to': mx_today - timedelta(days=1),
            },
        ])

    def test_no_request_when_already_synced_today(self):
        """A company already synced today is left alone."""
        company = self.env.company

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            company.l10n_mx_edi_last_sync = self._mx_today()
            # No mock entry: any call to SAT raises, which is how "nothing was sent" is asserted.
            with self.mocked_cfdi_requests([]):
                self._trigger_cron(self.company_cron)

        self.assertFalse(self.env['l10n_mx_edi.cfdi.request'].search_count([('company_id', '=', company.id)]))

    def test_request_starts_after_locked_period(self):
        """Assert that if there is a sync on a lock date, the request is created on the earliest day after the lock date."""
        company = self.env.company
        company.l10n_mx_edi_last_sync = False
        sat_accepts = {'response': self._build_request_download_response(request_type='batch_received')}

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            mx_today = self._mx_today()
            lock_date = mx_today - timedelta(days=2)
            company.fiscalyear_lock_date = lock_date
            company.invalidate_recordset()
            with self.mocked_cfdi_requests([sat_accepts, sat_accepts]):
                self._trigger_cron(self.company_cron)

        cfdi_requests = self.env['l10n_mx_edi.cfdi.request'].search([('company_id', '=', company.id)])
        self.assertRecordValues(cfdi_requests, [
            {
                'state': 'in_process_at_sat',
                'emission_date_from': lock_date + timedelta(days=1),
                'emission_date_to': mx_today - timedelta(days=1),
            },
            {
                'state': 'in_process_at_sat',
                'emission_date_from': lock_date + timedelta(days=1),
                'emission_date_to': mx_today - timedelta(days=1),
            },
        ])
        self.assertEqual(company.l10n_mx_edi_last_sync, mx_today)

    def test_no_request_when_whole_window_locked(self):
        """Assert situation when a lock lands on the `to date` of the synce, sync should wait until next day"""
        company = self.env.company
        cases = [
            ('locked up to today', 0),
            ('locked up to yesterday', 1),
        ]
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            mx_today = self._mx_today()
            for scenario, days_before_today in cases:
                with self.subTest(scenario=scenario):
                    company.l10n_mx_edi_last_sync = False
                    company.fiscalyear_lock_date = mx_today - timedelta(days=days_before_today)
                    company.invalidate_recordset()
                    with self.mocked_cfdi_requests([]):
                        self._trigger_cron(self.company_cron)

                    self.assertFalse(
                        self.env['l10n_mx_edi.cfdi.request'].search_count([('company_id', '=', company.id)]),
                    )
                    self.assertEqual(
                        company.l10n_mx_edi_last_sync,
                        company.fiscalyear_lock_date + timedelta(days=1),
                    )

    def test_only_eligible_mx_companies_are_picked(self):
        """The cron only picks MX companies with MXN currency, MX chart, and a valid e_firma."""
        company = self.env.company
        request_domain = [('company_id', '=', company.id)]

        # Each scenario fails one of the eligibility criteria.
        scenarios = [
            ('non-MX country', lambda: company.write({'account_fiscal_country_id': self.env.ref('base.us').id})),
            ('non-MXN currency', lambda: company.write({'currency_id': self.env.ref('base.USD').id})),
            ('non-MX chart template', lambda: company.write({'chart_template': False})),
            ('no e_firma scope', lambda: self.fiel_certificate.write({'scope': 'cfdi_csd'})),
        ]
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            for scenario, mutate in scenarios:
                with self.subTest(scenario=scenario), closing(self.env.cr.savepoint()):
                    company.l10n_mx_edi_last_sync = False
                    mutate()
                    with self.mocked_cfdi_requests([]):
                        self._trigger_cron(self.company_cron)
                    self.assertFalse(
                        self.env['l10n_mx_edi.cfdi.request'].search_count(request_domain),
                        f"Cron must skip company with {scenario}",
                    )

    def test_no_request_for_branch_company(self):
        branch = self.setup_other_company(name='MX Branch', parent_id=self.env.company.id)['company']
        branch_key = self.env['certificate.key'].create({
            'name': 'Branch key',
            'content': self.file_read('l10n_mx_edi/demo/pac_credentials/certificate.key'),
            'password': '12345678a',
            'company_id': branch.id,
        })
        branch_fiel = self.env['certificate.certificate'].create({
            'name': 'Branch FIEL',
            'content': self.file_read('l10n_mx_edi/demo/pac_credentials/certificate.cer'),
            'private_key_id': branch_key.id,
            'company_id': branch.id,
            'scope': 'e_firma',
        })
        branch_fiel.write({
            'date_start': self.frozen_today - timedelta(days=365),
            'date_end': self.frozen_today + timedelta(days=365),
        })
        # The parent is already synced today, so only the branch could be picked.
        self.env.company.l10n_mx_edi_last_sync = self._mx_today()

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            with self.mocked_cfdi_requests([]):
                self._trigger_cron(self.company_cron)

        self.assertFalse(self.env['l10n_mx_edi.cfdi.request'].search_count([('company_id', '=', branch.id)]))

    def test_create_requests_multi_company(self):
        other_company = self.setup_other_company(name='Other MX Company')['company']
        other_key = self.env['certificate.key'].create({
            'name': 'Test key B',
            'content': self.file_read('l10n_mx_edi/demo/pac_credentials/certificate.key'),
            'password': '12345678a',
            'company_id': other_company.id,
        })
        other_fiel = self.env['certificate.certificate'].create({
            'name': 'Test FIEL B',
            'content': self.file_read('l10n_mx_edi/demo/pac_credentials/certificate.cer'),
            'private_key_id': other_key.id,
            'company_id': other_company.id,
            'scope': 'e_firma',
        })
        other_fiel.write({
            'date_start': self.frozen_today - timedelta(days=365),
            'date_end': self.frozen_today + timedelta(days=365),
        })
        other_company.l10n_mx_edi_last_sync = False
        self.env.company.l10n_mx_edi_last_sync = False
        sat_accepts = {'response': self._build_request_download_response(request_type='batch_received')}

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            mx_today = self._mx_today()
            # Two receipt types for each of the two companies.
            with self.mocked_cfdi_requests([sat_accepts] * 4):
                self._trigger_cron(self.company_cron)

        for company in self.env.company + other_company:
            cfdi_requests = self.env['l10n_mx_edi.cfdi.request'].search(
                [('company_id', '=', company.id)], order='receipt_type',
            )
            self.assertRecordValues(cfdi_requests, [
                {'state': 'in_process_at_sat', 'request_uuid': DEFAULT_REQUEST_UUID, 'request_type': 'batch_received', 'receipt_type': 'I'},
                {'state': 'in_process_at_sat', 'request_uuid': DEFAULT_REQUEST_UUID, 'request_type': 'batch_received', 'receipt_type': 'E'},
            ])
            self.assertEqual(company.l10n_mx_edi_last_sync, mx_today)

    def test_create_requests_timezone(self):
        """Requests are created respecting the company's timezone."""
        company = self.env.company
        self.assertEqual(
            company.partner_id.commercial_partner_id._l10n_mx_edi_get_cfdi_timezone().key,
            'America/Guatemala',  # UTC-6
        )
        company.l10n_mx_edi_last_sync = False
        sat_accepts = {'response': self._build_request_download_response(request_type='batch_received')}
        # Time in UTC that resolves to the previous day in UTC-6.
        utc_instant = fields.Datetime.from_string('2025-06-15 03:00:00')
        mx_today = date(2025, 6, 14)  # UTC-6

        with self.mx_external_setup(utc_instant, certificate=self.fiel_certificate):
            with self.mocked_cfdi_requests([sat_accepts, sat_accepts]):
                self._trigger_cron(self.company_cron)

        cfdi_requests = self.env['l10n_mx_edi.cfdi.request'].search([('company_id', '=', company.id)])
        self.assertRecordValues(cfdi_requests, [
            {
                'emission_date_from': mx_today - timedelta(days=SAT_STAMP_LAG_DAYS),
                'emission_date_to': mx_today - timedelta(days=1),
            },
            {
                'emission_date_from': mx_today - timedelta(days=SAT_STAMP_LAG_DAYS),
                'emission_date_to': mx_today - timedelta(days=1),
            },
        ])
        self.assertEqual(company.l10n_mx_edi_last_sync, mx_today)

    def test_failed_sync_advance_and_notify(self):
        company = self.env.company
        sat_rejects = {'response': self._build_request_download_response(request_type='batch_received', status_code='5001')}
        sat_silent = {'error': requests.exceptions.ConnectionError('SAT is unreachable')}

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            mx_today = self._mx_today()
            cases = [
                ('SAT rejects', sat_rejects, '5001'),
                ('SAT never answers', sat_silent, 'SAT could not be reached'),
            ]
            for scenario, sat_answer, expected_cause in cases:
                with self.subTest(scenario=scenario), closing(self.env.cr.savepoint()):
                    company.l10n_mx_edi_last_sync = mx_today - timedelta(days=2)
                    with (
                        patch.object(self.env.registry['ir.cron'], '_notify_admin') as notify,
                        self.mocked_cfdi_requests([sat_answer, sat_answer]),
                    ):
                        self._trigger_cron(self.company_cron)

                    cfdi_requests = self.env['l10n_mx_edi.cfdi.request'].search([('company_id', '=', company.id)])
                    self.assertEqual(cfdi_requests.mapped('state'), ['rejected', 'rejected'])
                    self.assertEqual(len(notify.call_args_list), 1)
                    self.assertIn(company.display_name, notify.call_args.args[0])
                    self.assertIn(expected_cause, notify.call_args.args[0])
                    self.assertEqual(company.l10n_mx_edi_last_sync, mx_today)

    def test_partially_succeeded_company_request(self):
        """Assert that if a company request succeeds and then a later one not, the company advances and keep record or both."""
        company = self.env.company
        company.l10n_mx_edi_last_sync = False
        sat_accepts = {'response': self._build_request_download_response(request_type='batch_received')}
        sat_unreachable = {'error': requests.exceptions.ConnectionError('SAT is unreachable')}

        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            mx_today = self._mx_today()
            with self.mocked_cfdi_requests([sat_accepts, sat_unreachable]):
                self._trigger_cron(self.company_cron)

        cfdi_requests = self.env['l10n_mx_edi.cfdi.request'].search(
            [('company_id', '=', company.id)], order='receipt_type',  # I, then E
        )
        self.assertRecordValues(cfdi_requests, [
            {'receipt_type': 'I', 'state': 'in_process_at_sat', 'request_uuid': DEFAULT_REQUEST_UUID},
            {'receipt_type': 'E', 'state': 'rejected', 'request_uuid': False},
        ])
        self.assertEqual(company.l10n_mx_edi_last_sync, mx_today)

    def test_invalid_certificate_alerts_admin(self):
        company = self.env.company
        expired = {'date_end': self.frozen_today - timedelta(days=1)}
        archived = {'date_end': self.frozen_today - timedelta(days=1), 'active': False}

        with freeze_time(self.frozen_today):
            cases = [
                ('expired e.firma', expired, 2),
                ('expired e.firma, archived to opt out', archived, 0),
                ('no e.firma at all', {'scope': 'cfdi_csd'}, 0),
            ]
            for scenario, certificate_values, expected_alerts in cases:
                with self.subTest(scenario=scenario), closing(self.env.cr.savepoint()):
                    self.fiel_certificate.write(certificate_values)
                    with (
                        patch.object(self.env.registry['ir.cron'], '_notify_admin') as notify,
                        # No mock entry: reporting the company must cost no SAT call.
                        self.mocked_cfdi_requests([]),
                    ):
                        self._trigger_cron(self.company_cron)
                        self._trigger_cron(self.company_cron)

                    alerts = [call for call in notify.call_args_list if company.display_name in call.args[0]]
                    self.assertEqual(len(alerts), expected_alerts)
                    self.assertFalse(
                        self.env['l10n_mx_edi.cfdi.request'].search_count([('company_id', '=', company.id)]),
                    )
