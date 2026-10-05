from datetime import timedelta

from .common import TestMxEdiCommon
from odoo import Command, fields
from odoo.addons.mail.tools.discuss import Store
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import misc
from odoo.tools.misc import file_open

from freezegun import freeze_time

@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCFDIInvoiceWorkflow(TestMxEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_invoice_workflow(self):
        with freeze_time('2017-01-01'):
            invoice = self._create_invoice_mx(invoice_date_due='2017-02-01')  # Force PPD

        # No pac found.
        self.env.company.l10n_mx_edi_pac = None
        with freeze_time('2017-01-05'):
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [
            {
                'move_id': invoice.id,
                'datetime': fields.Datetime.from_string('2017-01-05 00:00:00'),
                'message': "No PAC specified.",
                'state': 'invoice_sent_failed',
                'sat_state': False,
                'cancellation_reason': False,
                'cancel_button_needed': False,
                'retry_button_needed': True,
            },
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': None}])

        # Set back the PAC but make it raising an error.
        self.env.company.l10n_mx_edi_pac = 'solfact'
        with freeze_time('2017-01-06'), self.with_mocked_pac_sign_error():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [
            {
                'move_id': invoice.id,
                'datetime': fields.Datetime.from_string('2017-01-06 00:00:00'),
                'message': "turlututu",
                'state': 'invoice_sent_failed',
                'sat_state': False,
                'cancellation_reason': False,
                'cancel_button_needed': False,
                'retry_button_needed': True,
            },
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': None}])

        # The failing attachment remains accessible for the user.
        self.assertTrue(invoice.l10n_mx_edi_invoice_document_ids.attachment_id)

        # Sign.
        with freeze_time('2017-01-07'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        sent_doc_values = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-01-07 00:00:00'),
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
            'show_button_needed': True,
            'receipt_type': 'I',
            'customer_rfc': self.partner_mx.vat,
        }])
        self.assertTrue(invoice.l10n_mx_edi_cfdi_attachment_id)
        self.assertTrue(invoice.l10n_mx_edi_invoice_document_ids.attachment_id)
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Cancel failed.
        self.env.company.l10n_mx_edi_pac = None
        with freeze_time('2017-02-01'):
            self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({'cancellation_reason': '02'}) \
                .action_cancel_invoice()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            {
                'move_id': invoice.id,
                'datetime': fields.Datetime.from_string('2017-02-01 00:00:00'),
                'message': "No PAC specified.",
                'state': 'invoice_cancel_failed',
                'sat_state': False,
                'cancellation_reason': '02',
                'cancel_button_needed': False,
                'retry_button_needed': True,
            },
            sent_doc_values,
        ])

        # Set back the PAC but make it raising an error.
        self.env.company.l10n_mx_edi_pac = 'solfact'
        with freeze_time('2017-02-06'), self.with_mocked_pac_cancel_error():
            invoice.l10n_mx_edi_invoice_document_ids.sorted()[0].action_retry()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            {
                'move_id': invoice.id,
                'datetime': fields.Datetime.from_string('2017-02-06 00:00:00'),
                'message': "turlututu",
                'state': 'invoice_cancel_failed',
                'sat_state': False,
                'cancellation_reason': '02',
                'cancel_button_needed': False,
                'retry_button_needed': True,
            },
            sent_doc_values,
        ])

        # Cancel.
        with freeze_time('2017-02-07'), self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({'cancellation_reason': '02'}) \
                .action_cancel_invoice()

        invoice.l10n_mx_edi_invoice_document_ids.invalidate_recordset(fnames=['cancel_button_needed'])
        sent_doc_values['cancel_button_needed'] = False

        cancel_doc_values = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-02-07 00:00:00'),
            'message': False,
            'state': 'invoice_cancel',
            'sat_state': 'not_defined',
            'cancellation_reason': '02',
            'cancel_button_needed': False,
            'retry_button_needed': False,
        }
        sent_doc_values['sat_state'] = 'skip'
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'state': 'cancel',
            'l10n_mx_edi_cfdi_state': 'cancel',
        }])

        # Sign again.
        invoice.button_draft()
        invoice.action_post()
        with freeze_time('2017-03-10'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        sent_doc_values2 = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-03-10 00:00:00'),
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Sat.
        with freeze_time('2017-04-01'), self.with_mocked_sat_call(lambda _x: 'valid'):
            invoice.l10n_mx_edi_cfdi_try_sat()
        sent_doc_values2['sat_state'] = 'valid'
        cancel_doc_values['sat_state'] = 'valid'
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Payment fully match but failed.
        payment1 = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-06-01',
                'amount': 100.0,
            })\
            ._create_payments()
        with freeze_time('2017-06-02'), self.with_mocked_pac_sign_error():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            {
                'move_id': payment1.move_id.id,
                'datetime': fields.Datetime.from_string('2017-06-02 00:00:00'),
                'message': "turlututu",
                'state': 'payment_sent_failed',
                'sat_state': False,
                'cancellation_reason': False,
                'cancel_button_needed': False,
                'retry_button_needed': True,
            },
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Unreconcile the payment.
        # The document should disappear.
        payment1.move_id.line_ids.remove_move_reconcile()
        with freeze_time('2017-06-02'):
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Redo the reconciliation.
        # The document should be created again.
        (invoice + payment1.move_id).line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .reconcile()
        with freeze_time('2017-06-03'), self.with_mocked_pac_sign_error():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            {
                'move_id': payment1.move_id.id,
                'datetime': fields.Datetime.from_string('2017-06-03 00:00:00'),
                'message': "turlututu",
                'state': 'payment_sent_failed',
                'sat_state': False,
                'cancellation_reason': False,
                'cancel_button_needed': False,
                'retry_button_needed': True,
            },
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # In case of success, the document is updated.
        with freeze_time('2017-06-04'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        payment1_doc_values1 = {
            'move_id': payment1.move_id.id,
            'datetime': fields.Datetime.from_string('2017-06-04 00:00:00'),
            'message': False,
            'state': 'payment_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment1_doc_values1,
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Call again the method shouldn't change anything.
        with freeze_time('2017-06-04'), self.with_mocked_pac_sign_error():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment1_doc_values1,
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Create another payment and unreconcile the first payment.
        payment2 = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-06-01',
                'amount': 100.0,
            })\
            ._create_payments()
        payment1.move_id.line_ids.remove_move_reconcile()
        with freeze_time('2017-07-01'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        payment2_doc_values1 = {
            'move_id': payment2.move_id.id,
            'datetime': fields.Datetime.from_string('2017-07-01 00:00:00'),
            'message': False,
            'state': 'payment_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment2_doc_values1,
            payment1_doc_values1,
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Fail to cancel the invoice.
        with freeze_time('2017-07-10'), self.with_mocked_pac_cancel_error():
            self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({'cancellation_reason': '02'}) \
                .action_cancel_invoice()
        cancel_doc_values2 = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-07-10 00:00:00'),
            'message': "turlututu",
            'state': 'invoice_cancel_failed',
            'sat_state': False,
            'cancellation_reason': '02',
            'cancel_button_needed': False,
            'retry_button_needed': True,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values2,
            payment2_doc_values1,
            payment1_doc_values1,
            sent_doc_values2,
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Reconcile again the first payment. Since this reconciliation has already been sent to the SAT, nothing
        # is updated.
        (invoice + payment1.move_id).line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .reconcile()
        with freeze_time('2017-07-11'), self.with_mocked_pac_sign_error():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(
            invoice.l10n_mx_edi_invoice_document_ids.sorted(lambda x: (x.datetime, x.move_id.id), reverse=True),
            [
                cancel_doc_values2,
                payment2_doc_values1,
                payment1_doc_values1,
                sent_doc_values2,
                cancel_doc_values,
                sent_doc_values,
            ],
        )
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Cancel successfully the invoice.
        with freeze_time('2017-07-12'), self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({'cancellation_reason': '02'}) \
                .action_cancel_invoice()

        invoice.l10n_mx_edi_invoice_document_ids.invalidate_recordset(fnames=['cancel_button_needed'])
        sent_doc_values2['cancel_button_needed'] = False

        cancel_doc_values2.update({
            'datetime': fields.Datetime.from_string('2017-07-12 00:00:00'),
            'message': False,
            'state': 'invoice_cancel',
            'sat_state': 'not_defined',
            'cancellation_reason': '02',
            'cancel_button_needed': False,
            'retry_button_needed': False,
        })
        self.assertRecordValues(
            invoice.l10n_mx_edi_invoice_document_ids.sorted(lambda x: (x.datetime, x.move_id.id), reverse=True),
            [
                cancel_doc_values2,
                payment2_doc_values1,
                payment1_doc_values1,
                sent_doc_values2,
                cancel_doc_values,
                sent_doc_values,
            ],
        )
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'cancel'}])

        with freeze_time('2017-07-12'), self.with_mocked_sat_call(lambda x: 'cancelled' if x.move_id == invoice else 'valid'):
            invoice.l10n_mx_edi_cfdi_try_sat()
        cancel_doc_values2['sat_state'] = 'cancelled'
        payment2_doc_values1['sat_state'] = 'valid'
        payment1_doc_values1['sat_state'] = 'valid'
        self.assertRecordValues(
            invoice.l10n_mx_edi_invoice_document_ids.sorted(lambda x: (x.datetime, x.move_id.id), reverse=True),
            [
                cancel_doc_values2,
                payment2_doc_values1,
                payment1_doc_values1,
                sent_doc_values2,
                cancel_doc_values,
                sent_doc_values,
            ],
        )
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'cancel'}])

    @freeze_time('2017-01-01')
    def test_action_show_document(self):
        """ Assert that action correctly points to the source records. """
        # Single invoice.
        invoice = self._create_invoice_mx()
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        invoice_doc = invoice.l10n_mx_edi_invoice_document_ids
        self.assertRecordValues(invoice_doc, [{'show_button_needed': True}])
        self.assertEqual(invoice_doc.action_show_document(), {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        })

        # Global invoice.
        gi_invoice1 = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
        gi_invoice2 = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
        gi_invoices = gi_invoice1 + gi_invoice2
        with self.with_mocked_pac_sign_success():
            self._create_invoices_global_invoice(gi_invoices)
        gi_doc = gi_invoices.l10n_mx_edi_invoice_document_ids
        self.assertRecordValues(gi_doc, [{'show_button_needed': True}])
        self.assertEqual(gi_doc.action_show_document(), {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', gi_invoices.ids)],
            'context': {'create': False},
            'name': 'Global Invoice',
        })

        # Payment.
        payment = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({'payment_date': '2017-01-01'})\
            ._create_payments()
        invoice.invalidate_recordset(fnames=['l10n_mx_edi_update_payments_needed'])
        with self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        payment_doc = payment.l10n_mx_edi_payment_document_ids
        self.assertRecordValues(payment_doc, [{'show_button_needed': True}])
        self.assertEqual(payment_doc.action_show_document(), payment.move_id.action_open_business_doc())

    def test_invoice_sent_after_paid(self):
        invoice = self._create_invoice_mx(invoice_date_due='2017-01-01')
        self.assertRecordValues(invoice, [{'l10n_mx_edi_payment_policy': 'PUE'}])

        # Pay.
        payment = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-06-01',
                'amount': 100.0,
            })\
            ._create_payments()

        # Sign.
        with freeze_time('2017-01-07'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        sent_doc_values = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-01-07 00:00:00'),
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_update_payments_needed': True}])

        with freeze_time('2017-06-02'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            {
                'move_id': payment.move_id.id,
                'datetime': fields.Datetime.from_string('2017-06-02 00:00:00'),
                'message': False,
                'state': 'payment_sent_pue',
                'sat_state': False,
                'cancel_button_needed': False,
                'retry_button_needed': False,
            },
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{'l10n_mx_edi_update_payments_needed': False}])

    def test_invoice_advanced_payment_flows(self):
        invoice = self._create_invoice_mx()
        self.assertRecordValues(invoice, [{'l10n_mx_edi_payment_policy': 'PPD'}])

        # Sign.
        with freeze_time('2017-01-07'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        sent_doc_values = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-01-07 00:00:00'),
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])

        # Pay.
        payment = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-06-01',
                'amount': 100.0,
            })\
            ._create_payments()

        # Try sending payment CFDI but force an error.
        with freeze_time('2017-06-03'), self.with_mocked_pac_sign_error():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            {
                'move_id': payment.move_id.id,
                'datetime': fields.Datetime.from_string('2017-06-03 00:00:00'),
                'message': "turlututu",
                'state': 'payment_sent_failed',
                'sat_state': False,
                'cancellation_reason': False,
                'cancel_button_needed': False,
                'retry_button_needed': True,
            },
            sent_doc_values,
        ])

        with freeze_time('2017-06-04'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        payment_doc_values = {
            'move_id': payment.move_id.id,
            'datetime': fields.Datetime.from_string('2017-06-04 00:00:00'),
            'message': False,
            'state': 'payment_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment_doc_values,
            sent_doc_values,
        ])

        # Cancel the payment.
        with freeze_time('2017-08-01'), self.with_mocked_pac_cancel_error():
            payment.l10n_mx_edi_payment_document_ids.action_cancel()
        payment_doc_cancel_values = {
            'move_id': payment.move_id.id,
            'datetime': fields.Datetime.from_string('2017-08-01 00:00:00'),
            'message': "turlututu",
            'state': 'payment_cancel_failed',
            'sat_state': False,
            'cancellation_reason': '02',
            'cancel_button_needed': False,
            'retry_button_needed': True,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment_doc_cancel_values,
            payment_doc_values,
            sent_doc_values,
        ])

        # Retry.
        with freeze_time('2017-08-02'), self.with_mocked_pac_cancel_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        payment_doc_cancel_values.update({
            'datetime': fields.Datetime.from_string('2017-08-02 00:00:00'),
            'message': False,
            'state': 'payment_cancel',
            'sat_state': 'not_defined',
            'cancellation_reason': '02',
            'cancel_button_needed': False,
            'retry_button_needed': False,
        })
        payment_doc_values['sat_state'] = 'skip'
        payment_doc_values['cancel_button_needed'] = False
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment_doc_cancel_values,
            payment_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # New payment.
        payment2 = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-08-01',
            })\
            ._create_payments()
        invoice.invalidate_recordset(fnames=['l10n_mx_edi_update_payments_needed'])
        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_update_payments_needed': True,
        }])
        with freeze_time('2017-08-03'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        payment2_doc_values = {
            'move_id': payment2.move_id.id,
            'datetime': fields.Datetime.from_string('2017-08-03 00:00:00'),
            'message': False,
            'state': 'payment_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment2_doc_values,
            payment_doc_cancel_values,
            payment_doc_values,
            sent_doc_values,
        ])

        # Remove it and again a new payment.
        payment2.move_id.line_ids.remove_move_reconcile()
        payment3 = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'amount': invoice.amount_residual,
                'payment_date': '2017-08-04',
            })\
            ._create_payments()

        with freeze_time('2017-08-04'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        payment3_doc_values = {
            'move_id': payment3.move_id.id,
            'datetime': fields.Datetime.from_string('2017-08-04 00:00:00'),
            'message': False,
            'state': 'payment_sent',
            'sat_state': 'not_defined',
            'cancellation_reason': False,
            'cancel_button_needed': True,
            'retry_button_needed': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment3_doc_values,
            payment2_doc_values,
            payment_doc_cancel_values,
            payment_doc_values,
            sent_doc_values,
        ])

        # Cancel payment2
        with freeze_time('2017-08-05'), self.with_mocked_pac_cancel_success():
            payment2.l10n_mx_edi_payment_document_ids.action_cancel()
        payment2_cancel_doc_values = {
            'move_id': payment2.move_id.id,
            'datetime': fields.Datetime.from_string('2017-08-05 00:00:00'),
            'message': False,
            'state': 'payment_cancel',
            'sat_state': 'not_defined',
            'cancellation_reason': '02',
            'cancel_button_needed': False,
            'retry_button_needed': False,
        }
        payment2_doc_values['sat_state'] = 'skip'
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment2_cancel_doc_values,
            payment3_doc_values,
            payment2_doc_values,
            payment_doc_cancel_values,
            payment_doc_values,
            sent_doc_values,
        ])

    def test_payment_on_multiple_invoices(self):
        invoice1 = self._create_invoice_mx_with_amount('2017-01-01', self.comp_curr, 1000.0)
        invoice2 = self._create_invoice_mx_with_amount('2017-01-01', self.comp_curr, 1000.0)

        # Sign.
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice1._l10n_mx_edi_cfdi_invoice_try_send()
        inv1_sent_doc_values = {
            'move_id': invoice1.id,
            'invoice_ids': invoice1.ids,
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids, [inv1_sent_doc_values])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # Create a payment with an higher amount than invoice1 and reconcile it.
        payment = self.env['account.payment'].create({
            'partner_id': self.partner_mx.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'date': invoice1.date,
            'amount': 1500.0,
            'currency_id': self.comp_curr.id,
        })
        payment.action_post()
        payment1_rec_line = payment.move_id.line_ids.filtered(lambda x: x.account_type == 'asset_receivable')
        invoice1_rec_line = invoice1.line_ids.filtered(lambda x: x.account_type == 'asset_receivable')
        (payment1_rec_line + invoice1_rec_line).reconcile()

        # Nothing change since the payment is not fully reconciled.
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice1.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids, [inv1_sent_doc_values])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # Fully reconcile the payment.
        invoice2_rec_line = invoice2.line_ids.filtered(lambda x: x.account_type == 'asset_receivable')
        (payment1_rec_line + invoice2_rec_line).reconcile()
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # Nothing change since invoice2 is not signed.
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice1.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids, [inv1_sent_doc_values])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # Sign invoice2 and retry the payments.
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice2._l10n_mx_edi_cfdi_invoice_try_send()
        invoice1.invalidate_recordset(fnames=['l10n_mx_edi_update_payments_needed'])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': True,
        }])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': True,
        }])
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice1.l10n_mx_edi_cfdi_invoice_try_update_payments()

        pay_sent_doc_values1 = {
            'move_id': payment.move_id.id,
            'invoice_ids': (invoice1 + invoice2).ids,
            'message': False,
            'state': 'payment_sent',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values1,
            inv1_sent_doc_values,
        ])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        inv2_sent_doc_values = {
            'move_id': invoice2.id,
            'invoice_ids': invoice2.ids,
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice2.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values1,
            inv2_sent_doc_values,
        ])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # Updating again the payment shouldn't do anything since the reconciliation hasn't changed.
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_error():
            invoice1.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values1,
            inv1_sent_doc_values,
        ])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice2.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values1,
            inv2_sent_doc_values,
        ])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # Change the reconciliation.
        invoice3 = self._create_invoice_mx_with_amount('2017-01-01', self.comp_curr, 1000.0)
        invoice2_rec_line.remove_move_reconcile()
        invoice3_rec_line = invoice3.line_ids.filtered(lambda x: x.account_type == 'asset_receivable')
        (payment1_rec_line + invoice3_rec_line).reconcile()
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice3._l10n_mx_edi_cfdi_invoice_try_send()
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_error():
            invoice1.l10n_mx_edi_cfdi_invoice_try_update_payments()
        pay_sent_doc_values2 = {
            'move_id': payment.move_id.id,
            'invoice_ids': (invoice1 + invoice3).ids,
            'message': "turlututu",
            'state': 'payment_sent_failed',
            'sat_state': False,
        }
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values2,
            pay_sent_doc_values1,
            inv1_sent_doc_values,
        ])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': True,
        }])
        self.assertRecordValues(invoice2.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values1,
            inv2_sent_doc_values,
        ])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        inv3_sent_doc_values = {
            'move_id': invoice3.id,
            'invoice_ids': invoice3.ids,
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice3.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values2,
            inv3_sent_doc_values,
        ])
        self.assertRecordValues(invoice3, [{
            'l10n_mx_edi_update_payments_needed': True,
        }])

        # Change again the reconciliation.
        invoice4 = self._create_invoice_mx_with_amount('2017-01-01', self.comp_curr, 1000.0)
        invoice1_rec_line.remove_move_reconcile()
        invoice4_rec_line = invoice4.line_ids.filtered(lambda x: x.account_type == 'asset_receivable')
        (payment1_rec_line + invoice4_rec_line).reconcile()
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice4._l10n_mx_edi_cfdi_invoice_try_send()
        with freeze_time('2017-01-02'), self.with_mocked_pac_sign_success():
            invoice4.l10n_mx_edi_cfdi_invoice_try_update_payments()
        pay_sent_doc_values2.update({
            'invoice_ids': (invoice3 + invoice4).ids,
            'message': False,
            'state': 'payment_sent',
            'sat_state': 'not_defined',
        })
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values1,
            inv1_sent_doc_values,
        ])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice3.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values2,
            inv3_sent_doc_values,
        ])
        self.assertRecordValues(invoice3, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        inv4_sent_doc_values = {
            'move_id': invoice4.id,
            'invoice_ids': invoice4.ids,
            'message': False,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice4.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values2,
            inv4_sent_doc_values,
        ])
        self.assertRecordValues(invoice4, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

        # Try to cancel the payment but it failed.
        self.assertRecordValues(payment.l10n_mx_edi_payment_document_ids.sorted(), [
            pay_sent_doc_values2,
            pay_sent_doc_values1,
        ])
        payment_doc = payment.l10n_mx_edi_payment_document_ids.sorted()[0]
        with freeze_time('2017-01-03'), self.with_mocked_pac_cancel_error():
            payment_doc.action_cancel()
        pay_cancel_doc_values = {
            'move_id': payment.move_id.id,
            'invoice_ids': (invoice3 + invoice4).ids,
            'message': "turlututu",
            'state': 'payment_cancel_failed',
            'sat_state': False,
        }
        self.assertRecordValues(payment.l10n_mx_edi_payment_document_ids.sorted(), [
            pay_cancel_doc_values,
            pay_sent_doc_values2,
            pay_sent_doc_values1,
        ])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice3.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_cancel_doc_values,
            pay_sent_doc_values2,
            inv3_sent_doc_values,
        ])
        self.assertRecordValues(invoice3, [{
            'l10n_mx_edi_update_payments_needed': True,
        }])
        self.assertRecordValues(invoice4.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_cancel_doc_values,
            pay_sent_doc_values2,
            inv4_sent_doc_values,
        ])
        self.assertRecordValues(invoice4, [{
            'l10n_mx_edi_update_payments_needed': True,
        }])

        # Change the reconciliation and successfully cancel.
        invoice3_rec_line.remove_move_reconcile()
        (payment1_rec_line + invoice1_rec_line).reconcile()
        payment_doc = payment.l10n_mx_edi_payment_document_ids.sorted()[0]
        with freeze_time('2017-01-03'), self.with_mocked_pac_cancel_success():
            payment_doc.action_retry()
        pay_cancel_doc_values.update({
            'invoice_ids': (invoice3 + invoice4).ids,
            'message': False,
            'state': 'payment_cancel',
            'sat_state': 'not_defined',
        })
        pay_sent_doc_values2['sat_state'] = 'skip'
        self.assertRecordValues(payment.l10n_mx_edi_payment_document_ids.sorted(), [
            pay_cancel_doc_values,
            pay_sent_doc_values2,
            pay_sent_doc_values1,
        ])
        self.assertRecordValues(invoice1.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_sent_doc_values1,
            inv1_sent_doc_values,
        ])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice2, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice3.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_cancel_doc_values,
            pay_sent_doc_values2,
            inv3_sent_doc_values,
        ])
        self.assertRecordValues(invoice3, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])
        self.assertRecordValues(invoice4.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_cancel_doc_values,
            pay_sent_doc_values2,
            inv4_sent_doc_values,
        ])
        self.assertRecordValues(invoice4, [{
            'l10n_mx_edi_update_payments_needed': False,
        }])

    @freeze_time('2017-01-01')
    def test_invoice_cancel_in_locked_period(self):
        invoice = self._create_invoice_mx(invoice_date_due='2017-02-01')
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        payment = self.env['account.payment.register'] \
            .with_context(active_model='account.move', active_ids=invoice.ids) \
            .create({}) \
            ._create_payments()
        with self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(payment, [{'l10n_mx_edi_cfdi_state': 'sent'}])

        # Lock the period.
        invoice.company_id.fiscalyear_lock_date = '2017-01-01'

        # Cancel the invoice.
        with self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({'cancellation_reason': '03'}) \
                .action_cancel_invoice()
        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'cancel'}])

        # Cancel the payment.
        with self.with_mocked_pac_cancel_success():
            payment.l10n_mx_edi_payment_document_ids.action_cancel()
        self.assertRecordValues(payment, [{'l10n_mx_edi_cfdi_state': 'cancel'}])

    def test_invoice_payment_production_sign_flow_cancel_from_the_sat(self):
        """ Test the case the invoice/payment is signed but the user manually cancel the document from the SAT portal (production environment). """
        self.env.company.l10n_mx_edi_pac_test_env = False
        self.env.company.l10n_mx_edi_pac_username = 'test'
        self.env.company.l10n_mx_edi_pac_password = 'test'

        with freeze_time('2017-01-01'):
            invoice = self._create_invoice_mx(invoice_date_due='2017-02-01')  # Force PPD
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            with self.with_mocked_sat_call(lambda _x: 'valid'):
                invoice.l10n_mx_edi_cfdi_try_sat()
            inv_sent_doc_values = {
                'move_id': invoice.id,
                'state': 'invoice_sent',
                'sat_state': 'valid',
            }
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [inv_sent_doc_values])
            self.assertRecordValues(invoice, [{
                'state': 'posted',
                'need_cancel_request': True,
                'show_reset_to_draft_button': False,
                'l10n_mx_edi_update_sat_needed': True,
                'l10n_mx_edi_cfdi_sat_state': 'valid',
                'l10n_mx_edi_cfdi_state': 'sent',
            }])

        # Register a payment and sign it.
        with freeze_time('2017-06-01'):
            payment = self.env['account.payment.register']\
                .with_context(active_model='account.move', active_ids=invoice.ids)\
                .create({'payment_date': '2017-06-01'})\
                ._create_payments()
            with self.with_mocked_pac_sign_success():
                invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
            pay_sent_doc_values = {
                'move_id': payment.move_id.id,
                'state': 'payment_sent',
                'sat_state': 'valid',
            }
            with self.with_mocked_sat_call(lambda _x: 'valid'):
                payment.move_id.l10n_mx_edi_cfdi_try_sat()
            self.assertRecordValues(payment.move_id.l10n_mx_edi_payment_document_ids, [pay_sent_doc_values])
            self.assertRecordValues(payment.move_id, [{
                'state': 'posted',
                'need_cancel_request': True,
                'show_reset_to_draft_button': False,
                'l10n_mx_edi_update_sat_needed': True,
                'l10n_mx_edi_cfdi_sat_state': 'valid',
                'l10n_mx_edi_cfdi_state': 'sent',
            }])

        # Manual cancellation from the SAT portal.
        with self.with_mocked_sat_call(lambda _x: 'cancelled'):
            invoice.l10n_mx_edi_cfdi_try_sat()

        inv_cancel_doc_values = {
            'move_id': invoice.id,
            'state': 'invoice_cancel',
            'sat_state': 'cancelled',
        }
        pay_cancel_doc_values = {
            'move_id': payment.move_id.id,
            'state': 'payment_cancel',
            'sat_state': 'cancelled',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            pay_cancel_doc_values,
            inv_cancel_doc_values,
            pay_sent_doc_values,
            inv_sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'state': 'cancel',
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'l10n_mx_edi_update_sat_needed': False,
            'l10n_mx_edi_cfdi_sat_state': 'cancelled',
            'l10n_mx_edi_cfdi_state': 'cancel',
        }])
        self.assertRecordValues(payment.move_id, [{
            'state': 'cancel',
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'l10n_mx_edi_update_sat_needed': False,
            'l10n_mx_edi_cfdi_sat_state': 'cancelled',
            'l10n_mx_edi_cfdi_state': 'cancel',
        }])

    def test_global_invoice_production_with_account_user(self):
        """ Test the global invoice creation made by a user that isn't in the group 'base.group_system' """
        self.simple_accountman.email = 'simple_accountman@test.com'

        with freeze_time('2017-01-01'):
            invoice = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice.with_user(self.simple_accountman))
            self.assertRecordValues(invoice, [{
                'l10n_mx_edi_cfdi_state': 'global_sent',
            }])

    def test_global_invoice_production_sign_flow_cancel_from_the_sat(self):
        """ Test the case the global invoice is signed but the user manually cancel the document from the SAT portal (production environment). """
        self.env.company.l10n_mx_edi_pac_test_env = False
        self.env.company.l10n_mx_edi_pac_username = 'test'
        self.env.company.l10n_mx_edi_pac_password = 'test'

        with freeze_time('2017-01-01'):
            invoice = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            with self.with_mocked_sat_call(lambda _x: 'valid'):
                invoice.l10n_mx_edi_cfdi_try_sat()
            sent_doc_values = {
                'invoice_ids': invoice.ids,
                'state': 'ginvoice_sent',
                'sat_state': 'valid',
            }
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])
            self.assertRecordValues(invoice, [{
                'l10n_mx_edi_update_sat_needed': True,
                'l10n_mx_edi_cfdi_sat_state': 'valid',
                'l10n_mx_edi_cfdi_state': 'global_sent',
            }])

        # Manual cancellation from the SAT portal.
        with self.with_mocked_sat_call(lambda _x: 'cancelled'):
            invoice.l10n_mx_edi_cfdi_try_sat()

        cancel_doc_values = {
            'invoice_ids': invoice.ids,
            'state': 'ginvoice_cancel',
            'sat_state': 'cancelled',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_update_sat_needed': False,
            'l10n_mx_edi_cfdi_sat_state': 'cancelled',
            'l10n_mx_edi_cfdi_state': 'global_cancel',
            'show_reset_to_draft_button': True,
        }])

    @freeze_time('2017-01-01')
    def test_invoice_production_sign_flow_cancel_from_odoo(self):
        """ Test the case the invoice is signed and the user request a cancellation in Odoo (production environment). """
        self.env.company.l10n_mx_edi_pac_test_env = False
        self.env.company.l10n_mx_edi_pac_username = 'test'
        self.env.company.l10n_mx_edi_pac_password = 'test'

        invoice = self._create_invoice_mx(invoice_date_due='2017-02-01')  # Force PPD
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        sent_doc_values = {
            'move_id': invoice.id,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])

        # Approval of the sat.
        with self.with_mocked_sat_call(lambda _x: 'valid'):
            invoice.l10n_mx_edi_cfdi_try_sat()
        sent_doc_values['sat_state'] = 'valid'
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])
        self.assertRecordValues(invoice, [{
            'state': 'posted',
            'need_cancel_request': True,
            'show_reset_to_draft_button': False,
            'l10n_mx_edi_update_sat_needed': True,
            'l10n_mx_edi_cfdi_sat_state': 'valid',
            'l10n_mx_edi_cfdi_state': 'sent',
        }])

        # Request Cancel.
        with self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(invoice.button_request_cancel()['context'])\
                .create({'cancellation_reason': '02'})\
                .action_cancel_invoice()
        cancel_request_doc_values = {
            'move_id': invoice.id,
            'state': 'invoice_cancel_requested',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_request_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'state': 'posted',
            'need_cancel_request': False,
            'show_reset_to_draft_button': False,
            'l10n_mx_edi_update_sat_needed': True,
            'l10n_mx_edi_cfdi_sat_state': 'not_defined',
            'l10n_mx_edi_cfdi_state': 'cancel_requested',
        }])

        # The SAT rejected the cancellation.
        with self.with_mocked_sat_call(lambda _x: 'valid'):
            invoice.l10n_mx_edi_cfdi_try_sat()
        cancel_request_doc_values['sat_state'] = 'valid'
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_request_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'state': 'posted',
            'need_cancel_request': True,
            'show_reset_to_draft_button': False,
            'l10n_mx_edi_update_sat_needed': True,
            'l10n_mx_edi_cfdi_sat_state': 'valid',
            'l10n_mx_edi_cfdi_state': 'sent',
        }])

        # Request Cancel again!
        with self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(invoice.button_request_cancel()['context'])\
                .create({'cancellation_reason': '02'})\
                .action_cancel_invoice()
        cancel_request_doc_values_2 = {
            'move_id': invoice.id,
            'state': 'invoice_cancel_requested',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_request_doc_values_2,
            cancel_request_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'state': 'posted',
            'need_cancel_request': False,
            'show_reset_to_draft_button': False,
            'l10n_mx_edi_update_sat_needed': True,
            'l10n_mx_edi_cfdi_sat_state': 'not_defined',
            'l10n_mx_edi_cfdi_state': 'cancel_requested',
        }])

        # The SAT approved the cancellation.
        with self.with_mocked_sat_call(lambda _x: 'cancelled'):
            invoice.l10n_mx_edi_cfdi_try_sat()
        cancel_doc_values = {
            'move_id': invoice.id,
            'state': 'invoice_cancel',
            'sat_state': 'cancelled',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values,
            cancel_request_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'state': 'cancel',
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'l10n_mx_edi_update_sat_needed': False,
            'l10n_mx_edi_cfdi_sat_state': 'cancelled',
            'l10n_mx_edi_cfdi_state': 'cancel',
        }])

    @freeze_time('2017-01-01')
    def test_invoice_test_sign_flow_cancel_from_odoo(self):
        """ Test the case the invoice is signed and the user request a cancellation in Odoo (testing environment). """
        invoice = self._create_invoice_mx(invoice_date_due='2017-02-01')  # Force PPD
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        sent_doc_values = {
            'move_id': invoice.id,
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])

        # Approval of the sat.
        with self.with_mocked_sat_call(lambda _x: 'valid'):
            invoice.l10n_mx_edi_cfdi_try_sat()
        sent_doc_values['sat_state'] = 'valid'
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])
        self.assertRecordValues(invoice, [{
            'state': 'posted',
            'need_cancel_request': True,
            'show_reset_to_draft_button': False,
            'l10n_mx_edi_update_sat_needed': True,
            'l10n_mx_edi_cfdi_sat_state': 'valid',
            'l10n_mx_edi_cfdi_state': 'sent',
        }])

        # Request Cancel.
        with self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(invoice.button_request_cancel()['context'])\
                .create({'cancellation_reason': '02'})\
                .action_cancel_invoice()
        cancel_doc_values = {
            'move_id': invoice.id,
            'state': 'invoice_cancel',
            'sat_state': 'not_defined',
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values,
            sent_doc_values,
        ])
        self.assertRecordValues(invoice, [{
            'state': 'cancel',
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'l10n_mx_edi_update_sat_needed': True,
            'l10n_mx_edi_cfdi_sat_state': 'not_defined',
            'l10n_mx_edi_cfdi_state': 'cancel',
        }])

    @freeze_time('2017-01-01')
    def test_payment_to_multiple_invoices_with_different_rfc(self):
        invoice1 = self._create_invoice_mx(partner_id=self.partner_mx.id, invoice_date_due='2017-02-01')
        invoice2 = self._create_invoice_mx(partner_id=self.partner_us.id, invoice_date_due='2017-02-01')

        with self.with_mocked_pac_sign_success():
            invoice1._l10n_mx_edi_cfdi_invoice_try_send()
            invoice2._l10n_mx_edi_cfdi_invoice_try_send()

        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': sum((invoice1 + invoice2).mapped('amount_total')),
            'date': '2017-01-01',
        })
        payment.action_post()
        (invoice1 + invoice2 + payment.move_id).line_ids\
            .filtered(lambda x: x.account_type == 'asset_receivable')\
            .reconcile()

        with self.with_mocked_pac_sign_success():
            invoice1.l10n_mx_edi_cfdi_invoice_try_update_payments()
        self.assertRecordValues(payment.l10n_mx_edi_payment_document_ids.sorted(), [
            {
                'move_id': payment.move_id.id,
                'invoice_ids': (invoice1 + invoice2).ids,
                'message': "You can't register a payment for invoices having different RFCs.",
                'state': 'payment_sent_failed',
            },
        ])

    @freeze_time('2017-01-01')
    def test_invoice_to_public_flow(self):
        invoice = self._create_invoice_mx(
            partner_id=self.partner_mx.id,
            l10n_mx_edi_cfdi_to_public=True,
        )
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        self.assertRecordValues(invoice, [{'l10n_mx_edi_cfdi_state': 'sent'}])
        self.assertEqual(len(invoice.l10n_mx_edi_invoice_document_ids), 1)

        self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({})\
            ._create_payments()
        with self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()

        self.assertEqual(len(invoice.l10n_mx_edi_invoice_document_ids), 2)

    @freeze_time('2017-01-01')
    def test_invoice_cancellation_01(self):
        # Create and send the invoice.
        invoice = self._create_invoice_mx()
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_cfdi_state': 'sent',
            'l10n_mx_edi_invoice_cancellation_reason': False,
            'l10n_mx_edi_cfdi_origin': False,
            'need_cancel_request': True,
            'show_reset_to_draft_button': False,
            'state': 'posted',
        }])

        # Create a replacement invoice.
        action_results = self.env['l10n_mx_edi.invoice.cancel'] \
            .with_context(invoice.button_request_cancel()['context']) \
            .create({}) \
            .action_create_replacement_invoice()
        new_invoice = self.env['account.move'].browse(action_results['res_id'])

        invoice.invalidate_recordset(fnames=['need_cancel_request', 'l10n_mx_edi_cfdi_cancel_id'])
        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_cfdi_state': 'sent',
            'l10n_mx_edi_invoice_cancellation_reason': False,
            'l10n_mx_edi_cfdi_origin': False,
            'need_cancel_request': False,
            'show_reset_to_draft_button': False,
            'l10n_mx_edi_cfdi_cancel_id': new_invoice.id,
            'state': 'posted',
        }])
        self.assertRecordValues(new_invoice, [{
            'l10n_mx_edi_cfdi_state': False,
            'l10n_mx_edi_invoice_cancellation_reason': False,
            'l10n_mx_edi_cfdi_origin': f'04|{invoice.l10n_mx_edi_cfdi_uuid}',
            'need_cancel_request': False,
            'show_reset_to_draft_button': False,
            'state': 'draft',
        }])

        # Sign the replacement invoice, which automatically cancels the old invoice.
        new_invoice.action_post()
        with self.with_mocked_pac_sign_success(), self.with_mocked_pac_cancel_success():
            new_invoice._l10n_mx_edi_cfdi_invoice_try_send()

        invoice.invalidate_recordset(fnames=['need_cancel_request', 'l10n_mx_edi_cfdi_cancel_id'])
        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_cfdi_state': 'cancel',
            'l10n_mx_edi_invoice_cancellation_reason': '01',
            'l10n_mx_edi_cfdi_origin': False,
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'l10n_mx_edi_cfdi_cancel_id': new_invoice.id,
            'state': 'cancel',
        }])

        self.assertRecordValues(new_invoice, [{
            'l10n_mx_edi_cfdi_state': 'sent',
            'l10n_mx_edi_invoice_cancellation_reason': False,
            'l10n_mx_edi_cfdi_origin': f'04|{invoice.l10n_mx_edi_cfdi_uuid}',
            'need_cancel_request': True,
            'show_reset_to_draft_button': False,
            'state': 'posted',
        }])

        # Cancel the replacement invoice.
        with self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(new_invoice.button_request_cancel()['context'])\
                .create({'cancellation_reason': '02'})\
                .action_cancel_invoice()

        self.assertRecordValues(new_invoice, [{
            'l10n_mx_edi_cfdi_state': 'cancel',
            'l10n_mx_edi_invoice_cancellation_reason': '02',
            'l10n_mx_edi_cfdi_origin': f'04|{invoice.l10n_mx_edi_cfdi_uuid}',
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'state': 'cancel',
        }])

    @freeze_time('2017-01-01')
    def test_invoice_cancellation_02(self):
        invoice = self._create_invoice_mx()
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_cfdi_state': 'sent',
            'l10n_mx_edi_invoice_cancellation_reason': False,
            'l10n_mx_edi_cfdi_origin': False,
            'need_cancel_request': True,
            'show_reset_to_draft_button': False,
            'state': 'posted',
        }])

        with self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({'cancellation_reason': '02'})\
                .action_cancel_invoice()
        self.assertRecordValues(invoice, [{
            'l10n_mx_edi_cfdi_state': 'cancel',
            'l10n_mx_edi_invoice_cancellation_reason': '02',
            'l10n_mx_edi_cfdi_origin': False,
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'state': 'cancel',
        }])

    @freeze_time('2017-01-01')
    def test_global_invoice_cancellation_01(self):
        # Create and send the invoice.
        invoice1 = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
        invoice2 = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
        invoices = invoice1 + invoice2

        # Sign as a global invoice.
        with self.with_mocked_pac_sign_success():
            self._create_invoices_global_invoice(invoices)
        sent_doc_values1 = {
            'invoice_ids': invoices.ids,
            'state': 'ginvoice_sent',
            'attachment_uuid': invoices[0].l10n_mx_edi_cfdi_uuid,
            'attachment_origin': False,
            'cancellation_reason': False,
        }
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids, [sent_doc_values1])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_cfdi_state': 'global_sent',
            'l10n_mx_edi_cfdi_uuid': sent_doc_values1['attachment_uuid'],
        }])

        # Request a replacement for the global invoice, which automatically cancels the original global invoice.
        gi_doc1 = invoices.l10n_mx_edi_invoice_document_ids
        with self.with_mocked_pac_sign_success(), self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(gi_doc1.action_request_cancel()['context'])\
                .create({})\
                .action_create_replacement_invoice()
        sent_doc_values2 = {
            'invoice_ids': invoices.ids,
            'state': 'ginvoice_sent',
            'attachment_uuid': invoices[0].l10n_mx_edi_cfdi_uuid,
            'attachment_origin': f"04|{sent_doc_values1['attachment_uuid']}",
            'cancellation_reason': False,
        }
        cancel_doc_values = {
            'invoice_ids': invoices.ids,
            'state': 'ginvoice_cancel',
            'attachment_uuid': sent_doc_values1['attachment_uuid'],
            'attachment_origin': False,
            'cancellation_reason': '01',
        }
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values,
            sent_doc_values2,
            sent_doc_values1,
        ])
        self.assertRecordValues(invoice1, [{
            'l10n_mx_edi_cfdi_state': 'global_sent',
            'l10n_mx_edi_cfdi_uuid': sent_doc_values2['attachment_uuid'],
        }])

    @freeze_time('2017-01-01')
    def test_global_invoice_then_replacement_then_cancel_replacement_then_cancel_gi(self):
        invoice1 = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
        invoice2 = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
        invoices = invoice1 + invoice2

        # Failed to send the global invoice.
        with self.with_mocked_pac_sign_error():
            invoices._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))
        sent_doc_values1 = {
            'move_id': None,
            'invoice_ids': invoices.ids,
            'message': "turlututu",
            'state': 'ginvoice_sent_failed',
            'sat_state': False,
            'attachment_uuid': False,
            'attachment_origin': False,
            'cancellation_reason': False,
            'retry_button_needed': True,
            'cancel_button_needed': False,
        }
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids, [sent_doc_values1])
        self.assertTrue(invoices.l10n_mx_edi_invoice_document_ids.attachment_id)

        # Successfully create the global invoice.
        with self.with_mocked_pac_sign_success():
            invoices.l10n_mx_edi_invoice_document_ids.action_retry()
        gi_attachment = invoices.l10n_mx_edi_cfdi_attachment_id
        self.assertEqual(len(gi_attachment), 1)
        sent_doc_values1.update({
            'message': False,
            'state': 'ginvoice_sent',
            'sat_state': 'not_defined',
            'attachment_id': gi_attachment.id,
            'attachment_uuid': invoices[0].l10n_mx_edi_cfdi_uuid,
            'attachment_origin': False,
            'retry_button_needed': False,
            'cancel_button_needed': True,
        })
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids, [sent_doc_values1])
        self.assertRecordValues(invoices, [{'l10n_mx_edi_update_sat_needed': True}] * 2)

        with self.with_mocked_sat_call(lambda _x: 'valid'):
            invoices[0].l10n_mx_edi_cfdi_try_sat()
        sent_doc_values1['sat_state'] = 'valid'
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids, [sent_doc_values1])

        # Request a replacement for the global invoice, automatically try to cancel the original invoice but fail.
        gi_doc1 = invoices.l10n_mx_edi_invoice_document_ids
        with self.with_mocked_pac_sign_success(), self.with_mocked_pac_cancel_error():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(gi_doc1.action_request_cancel()['context'])\
                .create({})\
                .action_create_replacement_invoice()

        gi_doc2 = invoices.l10n_mx_edi_invoice_document_ids.sorted()[1]
        self.assertTrue(gi_doc2.attachment_id)
        sent_doc_values2 = {
            'move_id': None,
            'invoice_ids': invoices.ids,
            'message': False,
            'state': 'ginvoice_sent',
            'sat_state': 'not_defined',
            'attachment_id': gi_doc2.attachment_id.id,
            'attachment_uuid': invoices[0].l10n_mx_edi_cfdi_uuid,
            'attachment_origin': f'04|{gi_doc1.attachment_uuid}',
            'cancellation_reason': False,
            'retry_button_needed': False,
            'cancel_button_needed': True,
        }
        gi_doc3 = invoices.l10n_mx_edi_invoice_document_ids.sorted()[0]
        self.assertTrue(gi_doc3.attachment_id)
        sent_doc_values3 = {
            'move_id': None,
            'invoice_ids': invoices.ids,
            'message': "turlututu",
            'state': 'ginvoice_cancel_failed',
            'sat_state': False,
            'attachment_id': gi_doc3.attachment_id.id,
            'attachment_uuid': gi_doc3.attachment_uuid,  # In this case, UUID does not become UUID of the invoices
            'attachment_origin': False,
            'cancellation_reason': '01',
            'retry_button_needed': True,
            'cancel_button_needed': False,
        }
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids.sorted(), [
            sent_doc_values3,
            sent_doc_values2,
            sent_doc_values1,
        ])

        # Failed to cancel the second global invoice with cancellation reason 02.
        with self.with_mocked_pac_cancel_error():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(gi_doc2.action_request_cancel()['context'])\
                .create({'cancellation_reason': '02'})\
                .action_cancel_invoice()
        cancel_doc_values1 = {
            'move_id': None,
            'invoice_ids': invoices.ids,
            'message': "turlututu",
            'state': 'ginvoice_cancel_failed',
            'sat_state': False,
            'attachment_id': gi_doc2.attachment_id.id,
            'attachment_uuid': gi_doc2.attachment_uuid,
            'attachment_origin': f'04|{gi_doc1.attachment_uuid}',
            'cancellation_reason': '02',
            'retry_button_needed': True,
            'cancel_button_needed': False,
        }
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values1,
            sent_doc_values2,
            sent_doc_values1,
        ])

        # Retry the cancellation of the second global invoice.
        with self.with_mocked_pac_cancel_success():
            invoices.l10n_mx_edi_invoice_document_ids.sorted()[0].action_retry()

        cancel_doc_values1.update({
            'message': False,
            'state': 'ginvoice_cancel',
            'sat_state': 'not_defined',
            'retry_button_needed': False,
            'cancel_button_needed': False,
        })
        sent_doc_values2['sat_state'] = 'skip'
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values1,
            sent_doc_values2,
            sent_doc_values1,
        ])

        # Successfully cancel the first global invoice.
        with self.with_mocked_pac_cancel_success():
            self.env['l10n_mx_edi.invoice.cancel']\
                .with_context(gi_doc1.action_request_cancel()['context'])\
                .create({})\
                .action_cancel_invoice()

        cancel_doc_values2 = {
            'move_id': None,
            'invoice_ids': invoices.ids,
            'message': False,
            'state': 'ginvoice_cancel',
            'sat_state': 'not_defined',
            'attachment_id': gi_doc1.attachment_id.id,
            'attachment_uuid': gi_doc1.attachment_uuid,
            'attachment_origin': False,
            'cancellation_reason': '01',
            'retry_button_needed': False,
            'cancel_button_needed': False,
        }
        self.assertRecordValues(invoices.l10n_mx_edi_invoice_document_ids.sorted(), [
            cancel_doc_values2,
            cancel_doc_values1,
            sent_doc_values2,
            sent_doc_values1,
        ])

    @freeze_time('2017-01-01')
    def test_global_invoice_after_failing_send_invoice(self):
        invoice = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)

        with self.with_mocked_pac_sign_error():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertEqual(len(invoice.l10n_mx_edi_invoice_document_ids), 1)
        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))
        self.assertEqual(len(invoice.l10n_mx_edi_invoice_document_ids), 1)

    def test_invoice_cancellation_then_replacement_in_foreign_currency(self):
        eff_date_1, date_1 = '2016-12-31', '2017-01-01'
        eff_date_2, date_2 = '2017-01-01', '2017-01-02'
        usd = self.setup_other_currency('USD', rates=[(eff_date_1, 1 / 17.187), (eff_date_2, 1 / 17.0357)])

        with freeze_time(date_1):
            # create an invoice in USD when currency rate is 0.05
            invoice = self._create_invoice_mx(
                invoice_date=date_1,
                date=date_1,
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 100,
                        'quantity': 1,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

        self.assertRecordValues(invoice.line_ids, [
            {
                'amount_currency': -100.0,
                'balance': -1718.7,
                'debit': 0.0,
                'credit': 1718.7,
            },
            {
                'amount_currency': -16.0,
                'balance': -274.99,
                'debit': 0.0,
                'credit': 274.99,
            },
            {
                'amount_currency': 116.0,
                'balance': 1993.69,
                'debit': 1993.69,
                'credit': 0.0,
            },
        ])

        # create a replacement invoice when currency rate is 17.0357
        with freeze_time(date_2):
            action_results = self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({}) \
                .action_create_replacement_invoice()
            new_invoice = self.env['account.move'].browse(action_results['res_id'])

        # the amounts of the replacement invoice should use the current rate
        self.assertRecordValues(new_invoice.line_ids, [
            {
                'amount_currency': -100.0,
                'balance': -1703.57,
                'debit': 0.0,
                'credit': 1703.57,
                'tax_base_amount': 0.0,
            },
            {
                'amount_currency': -16.0,
                'balance': -272.57,
                'debit': 0.0,
                'credit': 272.57,
                'tax_base_amount': -1703.57,
            },
            {
                'amount_currency': 116.0,
                'balance': 1976.14,
                'debit': 1976.14,
                'credit': 0.0,
                'tax_base_amount': 0.0,
            },
        ])

    def test_cannot_delete_edi_document(self):
        invoice = self._create_invoice_mx(invoice_date_due='2017-01-01')

        with freeze_time('2017-01-07'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertEqual(len(invoice.l10n_mx_edi_invoice_document_ids), 1)

        with self.assertRaises(UserError, msg="You can't unlink an attachment being an EDI document sent to the government."):
            invoice.l10n_mx_edi_invoice_document_ids.attachment_id.unlink()

    @freeze_time('2017-01-01 10:00:00')
    def test_global_invoice_year_month_format(self):
        """ Test that 'meses' and 'anno' are correctly set since we ignore them in
        other tests to allow to dynamically generate documents.
        """
        invoice = self._create_invoice_mx(
            l10n_mx_edi_cfdi_to_public=True,
            invoice_line_ids=[
                Command.create({
                    'product_id': self.product.id,
                    'price_unit': 1000.0,
                    'tax_ids': [],
                }),
            ],
        )
        with self.with_mocked_pac_sign_success():
            self._create_invoices_global_invoice(invoice)
        self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_global_invoice_year_month_format')

    def test_payment_workflow(self):
        """ Test the payment workflow, here is the flow we test :
                1) create and sign an invoice (PPD)
                2) create a first payment and send it
                3) unreconcile the first payment
                4) create a second payment with cfdi_origin referring the first payment uuid and send it
                5) cancel the first payment
                6) cancel the second payment
        """
        # Create invoice
        invoice = self._create_invoice_mx()

        # Sign.
        with freeze_time('2017-01-07'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        sent_doc_values = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-01-07 00:00:00'),
            'state': 'invoice_sent',
            'cancellation_reason': False,
            'attachment_origin': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])

        # Create new payment
        payment1 = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-06-01',
                'amount': 1160.0,
            })\
            ._create_payments()

        with freeze_time('2017-06-02'), self.with_mocked_pac_sign_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()

        payment1_doc_values = {
            'move_id': payment1.move_id.id,
            'datetime': fields.Datetime.from_string('2017-06-02 00:00:00'),
            'state': 'payment_sent',
            'cancellation_reason': False,
            'attachment_origin': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment1_doc_values,
            sent_doc_values,
        ])

        # Unreconcile the first payment
        payment1.move_id.line_ids.remove_move_reconcile()

        # Create a new payment with a cfdi origin containing the uuid of the first payment, which automatically cancels the first payment
        payment2 = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-06-01',
                'amount': 1160.0,
                'l10n_mx_edi_cfdi_origin': f'04|{payment1.l10n_mx_edi_cfdi_uuid}',
            })\
            ._create_payments()

        with freeze_time('2017-06-02'), self.with_mocked_pac_sign_success(), self.with_mocked_pac_cancel_success():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()

        payment2_doc_values = {
            'move_id': payment2.move_id.id,
            'datetime': fields.Datetime.from_string('2017-06-02 00:00:00'),
            'state': 'payment_sent',
            'cancellation_reason': False,
            'attachment_origin': f'04|{payment1.l10n_mx_edi_cfdi_uuid}',
        }
        payment1_cancel_doc_values = {
            'move_id': payment1.move_id.id,
            'datetime': fields.Datetime.from_string('2017-06-02 00:00:00'),
            'state': 'payment_cancel',
            'cancellation_reason': '01',
            'attachment_origin': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment1_cancel_doc_values,
            payment2_doc_values,
            payment1_doc_values,
            sent_doc_values,
        ])

        # Cancel the second payment, it should apply the cancellation reason '2'
        with freeze_time('2017-08-06'), self.with_mocked_pac_cancel_success():
            payment2.l10n_mx_edi_payment_document_ids.action_cancel()

        payment2_cancel_doc_values = {
            'move_id': payment2.move_id.id,
            'datetime': fields.Datetime.from_string('2017-08-06 00:00:00'),
            'state': 'payment_cancel',
            'cancellation_reason': '02',
            'attachment_origin': f'04|{payment1.l10n_mx_edi_cfdi_uuid}',
        }

        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment2_cancel_doc_values,
            payment1_cancel_doc_values,
            payment2_doc_values,
            payment1_doc_values,
            sent_doc_values,
        ])

    def test_access_invoice_form_with_second_user(self):
        def create_invoice(**kwargs):
            return self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                    })
                ],
                **kwargs
            )

        with self.mx_external_setup(self.frozen_today):
            second_partner = self.env['res.partner'].create({
                'name': 'second user',
            })
            second_user = self.env['res.users'].create({
                'login': 'seconduser',
                'partner_id': second_partner.id,
                'group_ids': [self.env.ref('account.group_account_manager').id]
            })

            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            invoice_for_global = create_invoice(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice_for_global)

            self.env.invalidate_all()  # remove values from cache to check access rights

            def invoice_fields(res: Store.FieldList):
                request_list = [
                    "activities",
                    "attachments",
                    "followers",
                    "scheduledMessages",
                    "suggestedRecipients",
                ]
                res.from_method("_store_thread_fields", request_list=request_list)

            store = Store()
            store.add(invoice.with_user(second_user), invoice_fields, as_thread=True)
            store.add(invoice_for_global.with_user(second_user), invoice_fields, as_thread=True)
            data = store._build_result()
            checksums = [attachment_data["checksum"] for attachment_data in data["ir.attachment"]]
            self.assertTrue(invoice.l10n_mx_edi_cfdi_attachment_id.checksum in checksums)
            self.assertTrue(invoice_for_global.l10n_mx_edi_cfdi_attachment_id.checksum in checksums)

    def test_cancel_payment(self):
        """ Test the payment cancelation workflow, here is the flow we test :
                1) create and sign an invoice
                2) create a payment and send it - it needs to fail in order to reset it to draft without requesting cancelation
                3) reset the payment to draft
                4) cancel the payment
        """
        # Create invoice
        invoice = self._create_invoice_mx()

        # Sign.
        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        sent_doc_values = {
            'move_id': invoice.id,
            'datetime': fields.Datetime.from_string('2017-01-01 00:00:00'),
            'state': 'invoice_sent',
            'cancellation_reason': False,
            'attachment_origin': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [sent_doc_values])

        # Create new payment with `Por Definir` payment method in order to fail the cfdi
        payment1 = self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-01-01',
                'amount': 1160.0,
            })\
            ._create_payments()

        with freeze_time('2017-01-01'), self.with_mocked_pac_sign_error():
            invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()

        payment1_doc_values = {
            'move_id': payment1.move_id.id,
            'datetime': fields.Datetime.from_string('2017-01-01 00:00:00'),
            'state': 'payment_sent_failed',
            'cancellation_reason': False,
            'attachment_origin': False,
        }
        self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids.sorted(), [
            payment1_doc_values,
            sent_doc_values,
        ])

        payment1.action_draft()
        payment1.action_cancel()

        self.assertFalse(payment1.move_id)
        self.assertEqual(payment1.state, 'canceled')

    def test_import_bill_write_l10n_mx_edi_cfdi_sat_state(self):
        """
        Test that when importing a cfdi bill, the field l10n_mx_edi_cfdi_sat_state is correctly computed
        """
        file_name = "test_import_bill"
        full_file_path = misc.file_path(f'{self.test_module}/tests/test_files/import/{file_name}.xml')

        self.env.company.partner_id.company_id = self.env.company

        with file_open(full_file_path, "rb") as file:
            file_content = file.read()
        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )
        self.assertEqual(new_bill.l10n_mx_edi_cfdi_sat_state, 'not_defined')
        self.assertRecordValues(new_bill.l10n_mx_edi_invoice_document_ids, [{
            'state': 'invoice_received',
            'customer_rfc': 'ICV060329BY0',
        }])

    def test_note_and_section_copied_new_invoice(self):
        """ Test that notes and sections are carry over when the new invoice is created after a cfdi cancel"""
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[
                Command.create({
                    'display_type': 'line_section',
                    'name': 'section',
                }),
                Command.create({
                    'display_type': 'line_note',
                    'name': 'note',
                }),
                Command.create({
                    'product_id': self.product.id,
                }),
            ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

        with self.with_mocked_pac_cancel_success():
            action_results = self.env['l10n_mx_edi.invoice.cancel'] \
                .with_context(invoice.button_request_cancel()['context']) \
                .create({'cancellation_reason': '01'}) \
                .action_create_replacement_invoice()

        new_invoice = self.env['account.move'].browse(action_results['res_id'])
        self.assertEqual(new_invoice.line_ids[0].name, 'section')
        self.assertEqual(new_invoice.line_ids[1].name, 'note')

    def test_cron_update_sat_state_write_date(self):
        """ Test that the sat_state write_date is updated on every cron run,
        retriggering within 4h skips recently checked documents, and vendor
        bills older than 7 days are excluded.
        """

        freeze_now = self.mock_datetime_and_now
        ref_datetime = fields.Datetime.from_string('2017-01-01 00:00:00')

        ref_datetime_minus_2 = ref_datetime - timedelta(days=2)
        with freeze_now(ref_datetime_minus_2):
            invoice_2 = self._create_invoice_mx()
            with self.with_mocked_pac_sign_success():
                invoice_2._l10n_mx_edi_cfdi_invoice_try_send()
            doc_2 = invoice_2.l10n_mx_edi_invoice_document_ids
            doc_2.invalidate_recordset()

        ref_datetime_minus_1 = ref_datetime - timedelta(days=1)
        with freeze_now(ref_datetime_minus_1):
            invoice_1 = self._create_invoice_mx()
            with self.with_mocked_pac_sign_success():
                invoice_1._l10n_mx_edi_cfdi_invoice_try_send()
            doc_1 = invoice_1.l10n_mx_edi_invoice_document_ids
            doc_1.invalidate_recordset()

        self.assertRecordValues(doc_1 + doc_2, [
            {'state': 'invoice_sent', 'write_date': ref_datetime_minus_1, 'sat_state': 'not_defined'},
            {'state': 'invoice_sent', 'write_date': ref_datetime_minus_2, 'sat_state': 'not_defined'},
        ])

        # Step 1: Run batch_size=1 where sat_state doesn't change (returns 'not_defined').
        # doc_2 (oldest create_date) is processed. write_date must update even if sat_state is unchanged.
        ref_datetime_plus_1 = ref_datetime + timedelta(days=1)
        with freeze_now(ref_datetime_plus_1), self.with_mocked_sat_call(lambda _x: 'not_defined'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(batch_size=1, extra_domain=[('id', 'in', (doc_1 + doc_2).ids)])
            doc_1.invalidate_recordset()
            doc_2.invalidate_recordset()
        self.assertRecordValues(doc_1 + doc_2, [
            {'state': 'invoice_sent', 'write_date': ref_datetime_minus_1, 'sat_state': 'not_defined'},
            {'state': 'invoice_sent', 'write_date': ref_datetime_plus_1, 'sat_state': 'not_defined'},
        ])

        cron = self.env.ref('l10n_mx_edi.ir_cron_update_pac_status_invoice')
        cron_trigger = self.env['ir.cron.trigger'].search([
            ('cron_id', '=', cron.id)
        ])
        self.assertEqual(
            cron_trigger.call_at,
            ref_datetime_plus_1,
            "The cron hasn't been retriggered for the remaining invoice !"
        )

        # Step 2: Immediate retrigger (1 minute later, < 4 hours).
        # doc_2 was updated 1m ago, so it must be skipped by write_date <= now - 4h filter.
        # doc_1 is processed instead.
        ref_datetime_plus_1_1m = ref_datetime_plus_1 + timedelta(minutes=1)
        with freeze_now(ref_datetime_plus_1_1m), self.with_mocked_sat_call(lambda _x: 'valid'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(batch_size=1, extra_domain=[('id', 'in', (doc_1 + doc_2).ids)])
            doc_1.invalidate_recordset()
            doc_2.invalidate_recordset()
        self.assertRecordValues(doc_1 + doc_2, [
            {'state': 'invoice_sent', 'write_date': ref_datetime_plus_1_1m, 'sat_state': 'valid'},
            {'state': 'invoice_sent', 'write_date': ref_datetime_plus_1, 'sat_state': 'not_defined'},
        ])

        # Step 3: Retrigger again 2 minutes later (< 4 hours).
        # doc_2 is skipped (< 4h since write_date), doc_1 is skipped (sat_state is 'valid').
        # No documents are fetched, so no cron retrigger occurs.
        cron_trigger.unlink()
        ref_datetime_plus_1_2m = ref_datetime_plus_1 + timedelta(minutes=2)
        with freeze_now(ref_datetime_plus_1_2m), self.with_mocked_sat_call(lambda _x: 'valid'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(batch_size=1, extra_domain=[('id', 'in', (doc_1 + doc_2).ids)])
        new_cron_trigger = self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])
        self.assertFalse(new_cron_trigger, "The cron should not retrigger when no remaining documents match domain")

        # Step 4: After > 4 hours (5 hours later), doc_2's write_date is > 4h ago, so it becomes eligible again.
        ref_datetime_plus_1_5h = ref_datetime_plus_1 + timedelta(hours=5)
        with freeze_now(ref_datetime_plus_1_5h), self.with_mocked_sat_call(lambda _x: 'valid'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(batch_size=1, extra_domain=[('id', 'in', (doc_1 + doc_2).ids)])
            doc_2.invalidate_recordset()
        self.assertEqual(doc_2.sat_state, 'valid')
        self.assertEqual(doc_2.write_date, ref_datetime_plus_1_5h)

        # Step 5: Test vendor bill (invoice_received) 7-day cutoff vs customer invoice 60-day cutoff
        ref_datetime_minus_10 = ref_datetime - timedelta(days=10)
        with freeze_now(ref_datetime_minus_10):
            vendor_bill_doc = self.env['l10n_mx_edi.document'].create({
                'state': 'invoice_received',
                'sat_state': 'not_defined',
                'datetime': ref_datetime_minus_10,
                'move_id': self._create_invoice_mx(move_type='in_invoice').id,
                'company_id': self.env.company.id,
            })
            customer_inv_doc = self.env['l10n_mx_edi.document'].create({
                'state': 'invoice_sent',
                'sat_state': 'not_defined',
                'datetime': ref_datetime_minus_10,
                'move_id': self._create_invoice_mx().id,
                'company_id': self.env.company.id,
            })

        ref_datetime_check = ref_datetime + timedelta(days=10)
        with freeze_now(ref_datetime_check), self.with_mocked_sat_call(lambda _x: 'valid'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(
                extra_domain=[('id', 'in', (vendor_bill_doc + customer_inv_doc).ids)]
            )
            vendor_bill_doc.invalidate_recordset()
            customer_inv_doc.invalidate_recordset()

        # Vendor bill created 20 days prior to check date (> 7 days) is NOT updated
        self.assertEqual(vendor_bill_doc.sat_state, 'not_defined')
        # Customer invoice created 20 days prior to check date (<= 60 days) IS updated
        self.assertEqual(customer_inv_doc.sat_state, 'valid')

        # Step 6: Test vendor bill write_date re-check threshold (12 hours) vs customer invoice (4 hours)
        ref_datetime_vb_create = ref_datetime - timedelta(days=2)
        with freeze_now(ref_datetime_vb_create):
            vendor_bill_recent = self.env['l10n_mx_edi.document'].create({
                'state': 'invoice_received',
                'sat_state': 'not_defined',
                'datetime': ref_datetime_vb_create,
                'move_id': self._create_invoice_mx(move_type='in_invoice').id,
                'company_id': self.env.company.id,

            })
            customer_inv_recent = self.env['l10n_mx_edi.document'].create({
                'state': 'invoice_sent',
                'sat_state': 'not_defined',
                'datetime': ref_datetime_vb_create,
                'move_id': self._create_invoice_mx().id,
                'company_id': self.env.company.id,
            })

        # Initial check at ref_datetime: both are processed and write_date becomes ref_datetime
        ref_datetime_vb_run = ref_datetime
        with freeze_now(ref_datetime_vb_run), self.with_mocked_sat_call(lambda _x: 'not_defined'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(
                extra_domain=[('id', 'in', (vendor_bill_recent + customer_inv_recent).ids)]
            )
            vendor_bill_recent.invalidate_recordset()
            customer_inv_recent.invalidate_recordset()
        self.assertEqual(vendor_bill_recent.write_date, ref_datetime_vb_run)
        self.assertEqual(customer_inv_recent.write_date, ref_datetime_vb_run)

        # 5 hours later: customer invoice IS re-checked (> 4h), vendor bill IS NOT re-checked (< 12h)
        ref_datetime_5h_later = ref_datetime_vb_run + timedelta(hours=5)
        with freeze_now(ref_datetime_5h_later), self.with_mocked_sat_call(lambda _x: 'valid'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(
                extra_domain=[('id', 'in', (vendor_bill_recent + customer_inv_recent).ids)]
            )
            vendor_bill_recent.invalidate_recordset()
            customer_inv_recent.invalidate_recordset()

        self.assertEqual(customer_inv_recent.sat_state, 'valid')
        self.assertEqual(vendor_bill_recent.sat_state, 'not_defined')

        # 13 hours later (> 12h): vendor bill IS now re-checked
        ref_datetime_13h_later = ref_datetime_vb_run + timedelta(hours=13)
        with freeze_now(ref_datetime_13h_later), self.with_mocked_sat_call(lambda _x: 'valid'):
            self.env['l10n_mx_edi.document']._fetch_and_update_sat_status(
                extra_domain=[('id', 'in', (vendor_bill_recent + customer_inv_recent).ids)]
            )
            vendor_bill_recent.invalidate_recordset()

        self.assertEqual(vendor_bill_recent.sat_state, 'valid')

    def test_payment_cfdi_with_leaked_default_type_context(self):
        """Test CFDI payment document creation with leaked context (default_type) from account.journal
        Requires documents_account to be installed (skipped otherwise).
        """
        if self.env['ir.module.module']._get('documents_account').state != 'installed':
            self.skipTest("documents_account is not installed")

        # Journal-folder sync is needed so the CFDI attachment creation triggers document creation
        bank_journal = self.company_data['default_journal_bank']
        folder = self.env['documents.document'].sudo().create({'name': 'Test Folder', 'type': 'folder'})
        if setting := self.env['documents.account.folder.setting'].sudo().search([
            ('journal_id', '=', bank_journal.id),
            ('company_id', '=', self.env.company.id)], limit=1):
            setting.folder_id = folder
        else:
            self.env['documents.account.folder.setting'].sudo().create({
                'folder_id': folder.id,
                'journal_id': bank_journal.id
                })

        invoice = self._create_invoice_mx()
        with freeze_time('2017-01-07'), self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        self.env['account.payment.register']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({
                'payment_date': '2017-06-01',
                'amount': 1160.0,
                'journal_id': bank_journal.id,
            })\
            ._create_payments()

        # Sign the payment CFDI with `default_type='sale'` context
        with freeze_time('2017-06-02'), self.with_mocked_pac_sign_success():
            invoice.with_context(default_type='sale').l10n_mx_edi_cfdi_invoice_try_update_payments()

        payment_doc = invoice.l10n_mx_edi_invoice_document_ids.filtered(lambda d: d.state == 'payment_sent')
        self.assertTrue(payment_doc, "Payment CFDI document should have been created")

        cfdi_attachment = payment_doc.attachment_id
        self.assertTrue(cfdi_attachment, "Payment CFDI attachment should exist")
        doc = self.env['documents.document'].search([('attachment_id', '=', cfdi_attachment.id)])
        self.assertTrue(doc, "A documents.document should have been created for the CFDI attachment")
        self.assertEqual(
            doc.type, 'binary',
            "Document type should be 'binary', not the leaked 'sale' value from the accounting context",
        )
