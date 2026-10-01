from unittest.mock import Mock, patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install', *AccountTestInvoicingCommon.extra_tags)
class TestGtFlow(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('gt')
    @AccountTestInvoicingCommon.setup_chart_template('gt')
    def setUpClass(cls):
        super().setUpClass()
        cls.tax_sale_b.fiscal_position_ids = cls.tax_sale_a.fiscal_position_ids
        cls.company.partner_id.write({
            'name': "My GT Company",
            'vat': '11201220K',
            'street': 'Guatemala street 121',
            'city': 'Guatemala City',
            'zip': '01010',
            'state_id': cls.env.ref('base.state_gt_gua').id,
            'l10n_gt_edi_phrase_ids': cls.env.ref('l10n_gt_edi.l10n_gt_edi_phrase_type_1_code_1').ids,
        })
        cls.partner_a.write({
            'name': "Empresa Guatemalteca S. A.",
            'vat': '2492334',
            'street': "Av. Pedro Calles. 434",
            'city': "Guatemala City",
            'zip': '01066',
            'state_id': cls.env.ref('base.state_gt_ave').id,
            'country_id': cls.env.ref('base.gt').id,
        })

        ChartTemplate = cls.env['account.chart.template']

        # ==== Taxes ====
        cls.iva_withholding = ChartTemplate.ref('tax_vat_withhold')
        cls.isr_withholding = ChartTemplate.ref('tax_isr_withhold')

    def test_fesp_vendor_bill_report_values_with_withholding_taxes(self):
        bill = self._create_invoice_one_line(
            move_type='in_invoice',
            product_id=self.product_a,
            tax_ids=self.iva_withholding | self.isr_withholding,
            l10n_gt_edi_doc_type='FESP',
        )
        bill.action_post()

        self.env['l10n_gt_edi.document'].create({'invoice_id': bill.id, 'state': 'invoice_sent'})
        values = bill._l10n_gt_edi_get_extra_invoice_report_values()

        self.assertIn('gran_total', values)
        self.assertIn('retencion_gran_total', values)

    def _create_invoice_gt(self, **invoice_args):
        invoice_args.setdefault('invoice_date', '2025-01-01')
        invoice = self._create_invoice(**invoice_args)
        invoice._compute_l10n_gt_edi_phrase_ids()
        invoice.action_post()
        return invoice

    def _get_gt_invoice_xml_element(self, invoice):
        invoice._l10n_gt_edi_try_send()
        self.assertEqual(invoice.l10n_gt_edi_state, 'invoice_sent')
        return invoice.l10n_gt_edi_attachment_id.raw.content

    def test_gt_edi_basic_invoice(self):
        invoice = self._create_invoice_gt()
        xml_data = self._get_gt_invoice_xml_element(invoice)
        self.assert_xml(xml_data, 'l10n_gt_edi_basic_invoice')

    def test_gt_edi_cui_partner(self):
        """A partner identified by a CUI is reported with it, not as an unidentified 'CF'."""
        self.partner_a.write({'vat': False, 'additional_identifiers': {'GT_CUI': '1234567890101'}})
        invoice = self._create_invoice_gt()

        gt_values = {}
        invoice._l10n_gt_edi_add_base_values(gt_values)

        self.assertEqual(gt_values['receptor_id'], '1234567890101')
        self.assertEqual(gt_values['receptor_tipo_especial'], 'CUI')
        self.assertNotIn('l10n_gt_edi_missing_vat', invoice._l10n_gt_edi_get_alerts())

    def test_nabn_available_only_for_vendor_credit_note(self):
        vendor_bill = self._create_invoice(move_type='in_invoice', company_id=self.company.id)
        vendor_bill_types = set(vendor_bill.l10n_gt_edi_available_doc_types.split(','))
        self.assertNotIn('NABN', vendor_bill_types)

        vendor_credit_note = self._create_invoice(move_type='in_refund', company_id=self.company.id)
        vendor_credit_note_types = set(vendor_credit_note.l10n_gt_edi_available_doc_types.split(','))
        self.assertIn('NABN', vendor_credit_note_types)

    def test_purchase_document_types_not_filtered_by_affiliation(self):
        move = self._create_invoice(move_type='in_invoice', company_id=self.company.id)
        available_types = set(move.l10n_gt_edi_available_doc_types.split(','))
        self.assertIn('FPEQ', available_types)
        self.assertIn('FCAP', available_types)

    def test_gt_edi_cancel_invoice(self):
        invoice = self._create_invoice_gt()
        invoice._l10n_gt_edi_try_send()
        self.assertEqual(invoice.l10n_gt_edi_state, 'invoice_sent')
        self.assertTrue(invoice.need_cancel_request)
        self.assertFalse(invoice.show_reset_to_draft_button)

        cancel_reason = "Test cancellation reason"
        cancel_wizard = self.env['l10n_gt_edi.cancel'].with_context(active_id=invoice.id).create({
            'l10n_gt_edi_cancel_reason': cancel_reason,
        })
        cancel_wizard.button_cancel()

        self.assertEqual(invoice.l10n_gt_edi_state, 'invoice_cancelled')
        self.assertEqual(invoice.state, 'cancel')

        cancel_doc = invoice.l10n_gt_edi_document_ids.filtered(lambda doc: doc.state == 'invoice_cancelled')
        self.assertTrue(cancel_doc)
        self.assertEqual(cancel_doc.cancel_reason, cancel_reason)

        report_values = invoice._l10n_gt_edi_get_extra_invoice_report_values()
        self.assertEqual(report_values['cancel_reason'], cancel_reason)
        self.assertTrue(report_values.get('cancel_date'))

        cancel_message = invoice.message_ids.filtered(lambda m: m.attachment_ids)
        self.assertIn(cancel_doc.attachment_id, cancel_message.attachment_ids)

        self.assert_xml(cancel_doc.attachment_id.raw.content, 'l10n_gt_edi_cancel_invoice')

    def test_gt_edi_cancel_invoice_error(self):
        invoice = self._create_invoice_gt()
        invoice._l10n_gt_edi_try_send()
        self.assertEqual(invoice.l10n_gt_edi_state, 'invoice_sent')

        sat_error_response = {
            'resultado': False,
            'fecha': '',
            'origen': '',
            'descripcion': '',
            'control_emision': {'Saldo': 0, 'Creditos': 0},
            'alertas_infile': False,
            'descripcion_alertas_infile': [],
            'alertas_sat': False,
            'descripcion_alertas_sat': [],
            'cantidad_errores': 1,
            'descripcion_errores': [{
                'resultado': False,
                'fuente': 'InFile',
                'categoria': '0',
                'numeral': '0',
                'validacion': '0',
                'mensaje_error': (
                    'El XML enviado no coincide con ninguno de los formatos '
                    'autorizados para la emision y/o anulacion de documentos en el regimen FEL.'
                ),
            }],
            'informacion_adicional': '',
            'serie': '',
            'uuid': '',
            'numero': 0,
            'xml_certificado': '',
        }
        mock_response = Mock()
        mock_response.json.return_value = sat_error_response

        cancel_wizard = self.env['l10n_gt_edi.cancel'].with_context(active_id=invoice.id).create({
            'l10n_gt_edi_cancel_reason': "Test cancellation",
        })
        self.company.l10n_gt_edi_service_provider = 'test'
        self.company.l10n_gt_edi_ws_prefix = 'test_user'
        self.company.l10n_gt_edi_infile_token = 'test_token'
        self.company.l10n_gt_edi_infile_key = 'test_key'
        with patch('odoo.addons.l10n_gt_edi.models.utils.requests.post', return_value=mock_response):
            with self.assertRaises(UserError):
                cancel_wizard.button_cancel()

        self.assertEqual(invoice.l10n_gt_edi_state, 'invoice_sent')
        self.assertEqual(invoice.state, 'posted')

    def test_credit_note_uses_original_invoice_date(self):
        """Test that the reference date for credit notes is the invoice_date of the original invoice."""

        invoice = self._create_invoice_one_line(
            move_type='out_invoice',
            product_id=self.product_a,
            invoice_date='2026-07-08',
            l10n_gt_edi_doc_type='FACT',
        )
        invoice.action_post()

        self.env['l10n_gt_edi.document'].create({
            'invoice_id': invoice.id,
            'state': 'invoice_sent',
            'datetime': '2026-07-17 07:42:31',
            'uuid': 'DEMO-UUID-1234',
            'serial_number': 'DEMO',
            'series': 'DEMO',
        })

        move_reversal = self.env['account.move.reversal'].with_context(active_model="account.move", active_ids=invoice.ids).create({
            'date': '2026-07-10',
            'reason': 'Test Reversal',
            'journal_id': invoice.journal_id.id,
        })
        reversal_action = move_reversal.refund_moves()
        credit_note = self.env['account.move'].browse(reversal_action['res_id'])
        credit_note.action_post()

        gt_values = {}
        credit_note._l10n_gt_edi_add_reference_values(gt_values)
        self.assertEqual(gt_values.get('referencias_fecha_emision_documento_origen'), '2026-07-08')
