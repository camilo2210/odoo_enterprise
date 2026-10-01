from datetime import datetime, timezone, timedelta

from odoo.tests import tagged
from odoo.tools.misc import file_open
from .common import TestEcEdiCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEcEdiFlow(TestEcEdiCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_send_invoice(self):
        ''' Test the delivery guide submission + cancellation flow. '''

        expected_operations = (
            (
                # First call: send the invoice
                'validarComprobante',
                {
                    'xml': file_open('l10n_ec_edi/tests/expected_files/sent_invoice.xml', 'rb').read(),
                },
                {
                    'estado': 'RECIBIDA',
                    'comprobantes': None,
                },
            ),
            (
                # Second call: retrieve the status
                'autorizacionComprobante',
                {'claveAccesoComprobante': '2501202201179236683600110010010000000013121521410'},
                {
                    'numeroComprobantes': '1',
                    'autorizaciones': {
                        'autorizacion': [{
                            'estado': 'AUTORIZADO',
                            'numeroAutorizacion': '2501202201179236683600110010010000000013121521410',
                            'fechaAutorizacion': datetime(2024, 12, 19, 12, 5, 29, tzinfo=timezone(timedelta(minutes=-5 * 60))),
                            'ambiente': 'PRUEBAS',
                            'comprobante': 'dummy',
                            'mensajes': None,
                        }],
                    },
                },
            ),
        )

        line_vals = self.get_invoice_line_vals(vat_tax_xmlid='tax_vat_05_510_sup_01')
        out_invoice = self.get_invoice(
            {
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
            },
            invoice_line_args=line_vals,
        )

        out_invoice.action_post()

        with self.mock_zeep_client(expected_operations):
            # Send the invoice
            out_invoice.button_process_edi_web_services()

    def test_provider_vat_alert(self):
        ''' Test the software provider RUC warning on an electronic document. '''
        out_invoice = self.get_invoice({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
        })
        company = self.company_data['company']

        # The company is its own software provider by default, and its RUC is a valid one
        self.assertEqual(company.l10n_ec_edi_provider_id, company.partner_id)
        self.assertNotIn('l10n_ec_edi_missing_provider_vat', (out_invoice.alerts or {}))

        company.l10n_ec_edi_provider_id = False
        self.assertIn('l10n_ec_edi_missing_provider_vat', (out_invoice.alerts or {}))

        provider = self.env['res.partner'].create({'name': "EC Software Provider"})
        company.l10n_ec_edi_provider_id = provider
        self.assertIn('l10n_ec_edi_missing_provider_vat', (out_invoice.alerts or {}))

        # A cédula is not enough, the SRI only accepts a 13 digit RUC
        provider.vat = '0453661050'
        self.assertIn('l10n_ec_edi_missing_provider_vat', (out_invoice.alerts or {}))

        provider.vat = '0453661050001'
        self.assertNotIn('l10n_ec_edi_missing_provider_vat', (out_invoice.alerts or {}))
        self.assertEqual(out_invoice._l10n_ec_get_invoice_additional_info()['RUC Proveedor'], '0453661050001')

    def test_provider_vat_alert_journal_without_edi(self):
        ''' Test that no warning is shown on a document that is not sent to the SRI. '''
        self.company_data['company'].l10n_ec_edi_provider_id = False
        in_invoice = self.get_invoice({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
        })
        self.assertNotIn('l10n_ec_edi_missing_provider_vat', (in_invoice.alerts or {}))
