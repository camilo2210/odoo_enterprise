from odoo.tests import tagged
from odoo.addons.account.tests.test_account_move_send import TestAccountMoveSendCommon
from odoo.addons.account_followup.tests.common import TestAccountFollowupCommon
from odoo.addons.mail.tests.common import MailCommon


@tagged('post_install', '-at_install')
class TestManualInvoiceFollowup(TestAccountMoveSendCommon, TestAccountFollowupCommon, MailCommon):

    _test_user_groups = None  # FIXME list needed groups

    def _assert_partner_mail_message_attchments(self, partner, expected_attachments):
        # reminder log is added on the partner, so fetch the message from the partner
        message = self._get_mail_message(partner)
        self.assertRecordValues(message.attachment_ids.sorted('name'), expected_attachments)

    def test_single_invoice_manual_followup(self):
        """
        Test single-invoice manual reminder behavior.

        The first send is treated as a regular invoice sending and only includes the
        invoice PDF attachment. The second send is treated as a reminder, so it
        includes both the open items report and the invoice PDF.
        """

        invoice = self.init_invoice("out_invoice", partner=self.partner_a.id, invoice_date='2026-01-01', amounts=[1000], post=True)
        # Send invoice
        wizard = self.create_send_and_print(invoice, sending_methods=['email'])
        wizard.action_send_and_print()
        invoice_pdf_values = {
            'mimetype': 'application/pdf',
            'name': 'INV_2026_00001.pdf',
            'placeholder': True,
        }
        self._assert_mail_attachments_widget(wizard, [invoice_pdf_values])

        # Resend invoice so it will be followup and attched open items report
        target_template = self.env.ref('account_followup.mail_template_invoice_payment_kind_reminder')
        wizard = self.create_send_and_print(invoice, sending_methods=['email'])
        wizard.template_id = target_template
        with self.allow_pdf_render():
            wizard.action_send_and_print()
        open_items_report_values = {
            'id': f'placeholder_{self._get_followup_file_name()}',
            'name': self._get_followup_file_name(),
            'mimetype': 'application/pdf',
            'placeholder': True,
            'dynamic_followup': True,
        }
        self._assert_mail_attachments_widget(wizard, [open_items_report_values, invoice_pdf_values])

        # Check that the attachments are correctly linked to the mail.message of the partner
        report_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', invoice.partner_id.id),
            ('name', 'like', self._get_followup_file_name()),
        ], limit=1)
        expected_attachment_values = [
            {
                'name': report_attachment.name,
                'raw': report_attachment.raw,
            },
            {
                'name': invoice.invoice_pdf_report_id.name,
                'raw': invoice.invoice_pdf_report_id.raw,
            },
        ]
        self._assert_partner_mail_message_attchments(self.partner_a, expected_attachment_values)

    def test_multiple_invoices_manual_followup(self):
        """
        Test multi-invoice manual reminder behavior in batch.

        In a first batch send, invoices are processed as regular invoice sending.
        When reminders are later sent for the same invoices, each partner receives
        the invoice PDF attachments plus one open items follow-up report.
        """

        def get_open_items_report_attachment(partner):
            return self.env['ir.attachment'].search([
                ('res_model', '=', 'res.partner'),
                ('res_id', '=', partner.id),
                ('name', 'like', self._get_followup_file_name()),
            ], limit=1)

        invoice1 = self.init_invoice("out_invoice", partner=self.partner_a.id, invoice_date='2026-01-01', amounts=[1000], post=True)
        invoice2 = self.init_invoice("out_invoice", partner=self.partner_a.id, invoice_date='2026-01-02', amounts=[1000], post=True)
        invoice3 = self.init_invoice("out_invoice", partner=self.partner_b.id, invoice_date='2026-01-03', amounts=[1000], post=True)
        moves = invoice1 + invoice2 + invoice3
        # Send invoice in batch
        wizard = self.create_send_and_print(moves)
        wizard.action_send_and_print()
        with self.enter_registry_test_mode():
            self.env.ref('account.ir_cron_account_move_send').method_direct_trigger()

        # Send reminder in batch
        wizard = self.env['account_followup.manual_reminder'].create(
            {
                'move_ids': moves.ids,
                'template_id': self.env.ref('account_followup.mail_template_partner_payment_kind_reminder', raise_if_not_found=False).id,
            }
        )
        with self.allow_pdf_render():
            wizard.send_reminder()

        # for parttner_a
        report_attachment = get_open_items_report_attachment(self.partner_a)
        expected_attachment_values = [
            {
                'name': report_attachment.name,
                'raw': report_attachment.raw,
            },
            {
                'name': invoice1.invoice_pdf_report_id.name,
                'raw': invoice1.invoice_pdf_report_id.raw,
            },
            {
                'name': invoice2.invoice_pdf_report_id.name,
                'raw': invoice2.invoice_pdf_report_id.raw,
            }
        ]
        self._assert_partner_mail_message_attchments(self.partner_a, expected_attachment_values)

        # for partner_b
        report_attachment = get_open_items_report_attachment(self.partner_b)
        expected_attachment_values = [
            {
                'name': report_attachment.name,
                'raw': report_attachment.raw,
            },
            {
                'name': invoice3.invoice_pdf_report_id.name,
                'raw': invoice3.invoice_pdf_report_id.raw,
            },
        ]
        self._assert_partner_mail_message_attchments(self.partner_b, expected_attachment_values)
