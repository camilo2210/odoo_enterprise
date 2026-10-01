import requests

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common_sat_download import (
    TestCfdiRequestCommon,
    DEFAULT_CFDI_UUID,
)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCfdiRequestWizard(TestCfdiRequestCommon):

    def _create_wizard(self, **vals):
        return self.env['l10n_mx_edi.cfdi.request.wizard'].create(vals)

    def test_wizard_sends_a_batch_request(self):
        """The wizard creates and sends a batch request."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            wizard = self._create_wizard(request_type='batch_issued', receipt_type='I', date_options='last_month')
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='batch_issued')):
                wizard.action_create_cfdi_request()
        request = self.env['l10n_mx_edi.cfdi.request'].search(
            [('request_type', '=', 'batch_issued')], order='id desc', limit=1,
        )
        self.assertRecordValues(request, [{
            'state': 'in_process_at_sat',
            'receipt_type': 'I',
            'emission_date_from': wizard.emission_date_from,
            'emission_date_to': wizard.emission_date_to,
        }])

    def test_wizard_sends_a_folio_request(self):
        """A folio wizard creates and sends a single-folio request."""
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            wizard = self._create_wizard(request_type='folio', cfdi_uuid=DEFAULT_CFDI_UUID)
            with self.mocked_send_cfdi_request(self._build_request_download_response(request_type='folio')):
                wizard.action_create_cfdi_request()
        request = self.env['l10n_mx_edi.cfdi.request'].search(
            [('request_type', '=', 'folio')], order='id desc', limit=1,
        )
        self.assertRecordValues(request, [{'state': 'in_process_at_sat', 'cfdi_uuid': DEFAULT_CFDI_UUID}])

    def test_wizard_request_rejection(self):
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            wizard = self._create_wizard(request_type='batch_issued', receipt_type='I', date_options='last_month')
            with self.mocked_send_cfdi_request(
                self._build_request_download_response(request_type='batch_issued', status_code='5002'),
            ):
                action = wizard.action_create_cfdi_request()

        request = self.env['l10n_mx_edi.cfdi.request'].search([], order='id desc', limit=1)
        self.assertRecordValues(request, [{'state': 'rejected'}])
        self.assertEqual(action['params']['type'], 'warning')
        self.assertEqual(action['params']['message'], request.message)

    def test_wizard_raises(self):
        with self.mx_external_setup(self.frozen_today, certificate=self.fiel_certificate):
            wizard = self._create_wizard(request_type='batch_issued', receipt_type='I', date_options='last_month')
            with self.mocked_failed_cfdi_request(
                error=requests.exceptions.ConnectionError('SAT is unreachable'),
            ):
                with self.assertRaisesRegex(UserError, 'SAT could not be reached'):
                    wizard.action_create_cfdi_request()

        self.assertFalse(self.env['l10n_mx_edi.cfdi.request'].search_count([]))

    def test_wizard_fills_dates_from_preset(self):
        """Assert that when using wizard date options, dates are correctly calculated."""
        with freeze_time('2025-06-15'):
            # Windows end yesterday in the company CFDI timezone.
            end = self._mx_today() - relativedelta(days=1)

            last_week = self._create_wizard(date_options='last_week')
            self.assertRecordValues(last_week, [{'emission_date_from': end - relativedelta(weeks=1), 'emission_date_to': end}])

            last_month = self._create_wizard(date_options='last_month')
            self.assertRecordValues(last_month, [{'emission_date_from': end - relativedelta(months=1), 'emission_date_to': end}])

            # A preset only suggests the window: the dates stay editable on top of it.
            custom_from, custom_to = fields.Date.from_string('2025-01-01'), fields.Date.from_string('2025-01-31')
            edited = self._create_wizard(
                date_options='last_month',
                emission_date_from=custom_from,
                emission_date_to=custom_to,
            )
            self.assertRecordValues(edited, [{'emission_date_from': custom_from, 'emission_date_to': custom_to}])
