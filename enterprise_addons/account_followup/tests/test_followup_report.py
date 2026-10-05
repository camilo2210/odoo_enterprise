# -*- coding: utf-8 -*-
from contextlib import contextmanager
from freezegun import freeze_time
from unittest.mock import patch

from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.account_followup.tests.common import TestAccountFollowupCommon
from odoo.addons.base.tests.files import PDF_RAW
from odoo import Command, fields


@tagged('post_install', '-at_install')
class TestAccountFollowupReports(TestAccountReportsCommon, TestAccountFollowupCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_a.email = 'partner_a@mypartners.xyz'
        cls.report = cls.env.ref('account_reports.followup_report')

    def test_followup_report_address_1(self):
        ''' Test child contact priorities: the company will be used when there is no followup or billing contacts
        '''

        Partner = self.env['res.partner']
        options = {
            'partner_id': self.partner_a.id,
        }

        child_partner = Partner.create({
            'name': "Child contact",
            'type': "contact",
            'parent_id': self.partner_a.id,
        })

        mail = self.env['mail.mail'].search([('recipient_ids', '=', self.partner_a.id)])
        self._create_invoice_followup(invoice_date='2016-01-01', partner=child_partner.id)
        with patch.object(type(self.env['mail.mail']), 'unlink', lambda self: None):
            with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': 'fake_partner_ledger.pdf', 'file_content': b'', 'file_type': 'pdf'}):
                self.env['account.followup.report']._send_email(options)

        mail = self.env['mail.mail'].search([('recipient_ids', '=', self.partner_a.id)])
        self.assertTrue(mail, "The payment reminder email should have been sent to the company.")

    def test_followup_report_address_2(self):
        ''' Test child contact priorities: the follow up contact will be preferred over the billing contact
        '''

        Partner = self.env['res.partner']
        options = {
            'partner_id': self.partner_a.id,
        }

        # Testing followup sent to billing address if used in invoice

        child_partner = Partner.create({
            'name': "Child contact",
            'type': "contact",
            'parent_id': self.partner_a.id,
        })
        invoice_partner = Partner.create({
            'name' : "Child contact invoice",
            'type' : "invoice",
            'email' : "test-invoice@example.com",
            'parent_id': child_partner.id,
        })

        self._create_invoice_followup(invoice_date='2016-01-01', partner=invoice_partner.id)

        with patch.object(type(self.env['mail.mail']), 'unlink', lambda self: None):
            with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': 'fake_partner_ledger.pdf', 'file_content': b'', 'file_type': 'pdf'}):
                self.env['account.followup.report']._send_email(options)

        mail = self.env['mail.mail'].search([('recipient_ids', '=', invoice_partner.id)])
        self.assertTrue(mail, "The payment reminder email should have been sent to the invoice partner.")
        mail.unlink()

    def test_negative_followup_report(self):
        ''' Test negative or null followup reports: if a contact has an overdue invoice but has a negative of null total due, no action is needed.
        '''
        followup_line = self.create_followup(delay=15)
        self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)

        self.env['account.move'].create({
            'move_type': 'out_refund',
            'invoice_date': '2016-01-15',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 300,
                'tax_ids': [],
            })]
        }).action_post()
        self.assertEqual(self.partner_a.total_due, 200)
        self.assertPartnerFollowup(self.partner_a, followup_line)

        self.env['account.payment'].create({
            'partner_id': self.partner_a.id,
            'amount': 400,
        }).action_post()
        self.assertEqual(self.partner_a.total_due, -200)
        self.assertPartnerFollowup(self.partner_a, followup_line)

    def test_process_automatic_followup_send_email(self):
        """ Tests that the email address in the mail.template is used to send the followup email from the cron."""
        followup_line = self.create_followup(delay=15)

        @contextmanager
        def create_and_send_email(email_from, subject):
            """ Create a mail.template, link it with the followup line and execute followups."""
            mail_template = self.env['mail.template'].create({
                'name': "Payment Reminder",
                'model_id': self.env.ref('base.model_res_partner').id,
                'email_from': email_from,
                'partner_to': '{{ object.id }}',
                'subject': subject,
            })
            followup_line.mail_template_id = mail_template
            with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': 'fake_partner_ledger.pdf', 'file_content': b'', 'file_type': 'pdf'}):
                self._execute_followup(self.partner_a)
            yield
            self.assertEqual(len(message), 1)
            self.assertEqual(message.author_id, self.partner_a._get_followup_responsible().partner_id, "Automatic followups should have the followup responsible as the author.")

        # case 1: the email_from is dynamically set
        inv1 = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)
        with create_and_send_email(
            email_from="{{ object._get_followup_responsible().email_formatted }}",
            subject="{{ (object.company_id or object._get_followup_responsible().company_id).name }} Pay me now !",
        ):
            message = self.env['mail.message'].search([('subject', 'like', "Pay me now !")])
            self.assertEqual(message.email_from, self.env.user.partner_id.email_formatted)

        # we have to create a new overdue invoice and reconcile the previous one to test the second case.
        # will no longer trigger the followup
        self.env['account.payment.register'].create({
                'line_ids': inv1.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

        # case 2: the email_from is hardcoded in the template
        self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id, price_unit=600)
        with create_and_send_email(
            email_from="test@odoo.com",
            subject="{{ (object.company_id or object._get_followup_responsible().company_id).name }} Pay me noooow !",
        ):
            message = self.env['mail.message'].search([('subject', 'like', "Pay me noooow !")])
            self.assertEqual(message.email_from, "test@odoo.com")

    def test_followup_report_with_levels_on_main_company(self):
        cron = self.env.ref('account_followup.ir_cron_follow_up')
        self.company_data['company'].automatic_invoice_reminder = True

        followup_15 = self.create_followup(delay=15)

        _followup_30 = self.create_followup(delay=30)

        inv = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)

        # Get receivable aml
        aml = inv.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        # Before cron → no followup level
        self.assertFalse(aml.followup_line_id)
        with (
            freeze_time('2022-01-10'),
            patch.object(self.env.registry['res.partner'], '_send_followup') as patched,
            self.enter_registry_test_mode(),
            patch.object(self.env.registry['ir.actions.report'], '_run_pdf_engine_without_processing', return_value=b"0"),
        ):
            cron.method_direct_trigger()
            # For the same reason we clear the cache in assertPartnerFollowup, to avoid this test change the state of the cache,
            # which could break other tests.
            self.env.cr.cache.pop('res_partner_all_followup', None)
            self.assertEqual(patched.call_count, 1)

        # After cron → lowest eligible followup level must be assigned
        self.assertEqual(aml.followup_line_id.id, followup_15.id)

    def test_followup_report_with_levels_on_one_branch(self):
        cron = self.env.ref('account_followup.ir_cron_follow_up')
        self.company_data['company'].automatic_invoice_reminder = True

        branch_a, branch_b = self.env['res.company'].create([{
            'name': 'Branch number 1',
            'parent_id': self.company_data['company'].id,
            'automatic_invoice_reminder': True,
        }, {
            'name': 'Branch number 2',
            'parent_id': self.company_data['company'].id,
            'automatic_invoice_reminder': True,
        }])

        self.cr.precommit.run()  # load the COA

        followup15 = self.create_followup(delay=15, company_id=branch_a.id)
        _followup30 = self.create_followup(delay=30, company_id=branch_a.id)

        inv1 = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id, company_id=branch_a.id, price_unit=400)
        inv2 = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id, company_id=branch_b.id, price_unit=800)

        # Get receivable aml
        aml1 = inv1.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        aml2 = inv2.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        # Before cron → no followup level
        self.assertFalse(aml1.followup_line_id + aml2.followup_line_id)
        with (
            freeze_time('2022-01-10'),
            patch.object(self.env.registry['res.partner'], '_send_followup') as patched,
            self.enter_registry_test_mode(),
            patch.object(self.env.registry['ir.actions.report'], '_run_pdf_engine_without_processing', return_value=b"0"),
        ):
            cron.method_direct_trigger()
            # For the same reason we clear the cache in assertPartnerFollowup, to avoid this test change the state of the cache,
            # which could break other tests.
            self.env.cr.cache.pop('res_partner_all_followup', None)
            self.assertEqual(patched.call_count, 1)

        # After cron → lowest eligible followup level must be assigned for branch_a and no followup should be assigned for branch_b
        self.assertEqual(aml1.followup_line_id.id, followup15.id)
        self.assertFalse(aml2.followup_line_id)

    def test_followup_report_with_levels_on_branches_and_main_company(self):
        cron = self.env.ref('account_followup.ir_cron_follow_up')
        self.company_data['company'].automatic_invoice_reminder = True

        branch_a, branch_b = self.env['res.company'].create([{
            'name': 'Branch number 1',
            'parent_id': self.company_data['company'].id,
            'automatic_invoice_reminder': True,
        }, {
            'name': 'Branch number 2',
            'parent_id': self.company_data['company'].id,
            'automatic_invoice_reminder': True,
        }])

        self.cr.precommit.run()  # load the COA

        a_followup15 = self.create_followup(delay=15, company_id=branch_a.id)
        _a_followup30 = self.create_followup(delay=30, company_id=branch_a.id)
        b_followup10 = self.create_followup(delay=10, company_id=branch_b.id)
        _b_followup20 = self.create_followup(delay=20, company_id=branch_b.id)
        parent_followup20 = self.create_followup(delay=20)
        _parent_followup40 = self.create_followup(delay=40)

        inv1 = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id, company_id=branch_a.id, price_unit=400)
        inv2 = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id, company_id=branch_b.id, price_unit=800)
        inv3 = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id, price_unit=200)

        # Get receivable aml
        aml1 = inv1.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        aml2 = inv2.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        aml3 = inv3.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        # Before cron → no followup level
        self.assertFalse(aml1.followup_line_id + aml2.followup_line_id + aml3.followup_line_id)

        with (
            freeze_time('2022-01-10'),
            patch.object(self.env.registry['res.partner'], '_send_followup') as patched,
            self.enter_registry_test_mode(),
            patch.object(self.env.registry['ir.actions.report'], '_run_pdf_engine_without_processing', return_value=b"0"),
        ):
            cron.method_direct_trigger()
            # For the same reason we clear the cache in assertPartnerFollowup, to avoid this test change the state of the cache,
            # which could break other tests.
            self.env.cr.cache.pop('res_partner_all_followup', None)
            self.assertEqual(patched.call_count, 3)

        # After cron → lowest eligible followup level must be assigned for branch_a and branch_b and main company
        self.assertEqual(aml1.followup_line_id.id, a_followup15.id)
        self.assertEqual(aml2.followup_line_id.id, b_followup10.id)
        self.assertEqual(aml3.followup_line_id.id, parent_followup20.id)

        # Now we check the amounts overdue
        # Expected : 200 (main_company) + 400 (branch_a) + 800 (branch_b)
        self.assertEqual(self.partner_a.total_overdue, 1400)
        # Expected : 400
        self.assertEqual(self.partner_a.with_company(branch_a).total_overdue, 400)
        # Expected : 800
        self.assertEqual(self.partner_a.with_company(branch_b).total_overdue, 800)

    def test_partner_total_due_with_payable(self):
        """
        Test that the total due for a partner also reflects payable accounts and is coherent with the customer statement report.
        """
        # Init options.
        report = self.env.ref('account_reports.customer_statement_report')
        default_options = {
            'partner_id': self.partner_a.id,
            'multi_currency': True,
            'unfold_all': True,
        }
        options = self._generate_options(report, '2016-01-01', '2016-12-31', default_options=default_options)

        self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)

        self.assertRecordValues(self.partner_a, [{'total_due': 500.0, 'total_all_due': 500.0}])

        with freeze_time('2016-01-01'):
            self.assertLinesValues(
                # pylint: disable=C0326
                report._get_lines(options),
                #   Name                                        Date,        Due Date,  Amount
                [   0,                                      1,              2,       3],
                [
                    ('Customer Statement',                         '',             '',   500.0),
                    ('partner_a',                                  '',             '',   500.0),
                    ('INV/2016/00001',                   '01/01/2016',   '01/01/2016',   500.0),
                    ('Total partner_a',                            '',             '',   500.0),
                    ('Total Customer Statement',                   '',             '',   500.0),
                ],
                options,
            )

        self.init_invoice('in_invoice', self.partner_a, '2016-01-01', True, amounts=[200])

        self.assertRecordValues(self.partner_a, [{'total_due': 500.0, 'total_all_due': 300.0}])

        with freeze_time('2016-01-01'):
            self.assertLinesValues(
                # pylint: disable=C0326
                report._get_lines(options),
                #   Name                                        Date,        Due Date,  Amount
                [   0,                                      1,              2,       3],
                [
                    ('Customer Statement',                         '',             '',   300.0),
                    ('partner_a',                                  '',             '',   300.0),
                    ('INV/2016/00001',                   '01/01/2016',   '01/01/2016',   500.0),
                    ('BILL/2016/01/0001',                '01/01/2016',   '01/01/2016',  -200.0),
                    ('Total partner_a',                            '',             '',   300.0),
                    ('Total Customer Statement',                   '',             '',   300.0),
                ],
                options,
            )

    def test_automatic_followup_report_attachments(self):
        followup_line = self.create_followup(delay=15)
        invoice = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)

        self.assertPartnerFollowup(self.partner_a, followup_line)

        send_wizard = self.env['account.move.send.wizard']\
            .with_context(active_model='account.move', active_ids=invoice.ids)\
            .create({'sending_methods': ['manual']})
        send_wizard.action_send_and_print()

        with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': self._get_followup_file_name(), 'file_content': b'', 'file_type': 'pdf'}):
            self.partner_a.action_manually_process_automatic_followups()

        sent_attachments = self.env['mail.message'].search([('partner_ids', '=', self.partner_a.id)]).attachment_ids
        self.assertEqual(sent_attachments.mapped('name'), [self._get_followup_file_name(), invoice._get_invoice_report_filename()])

    def test_manual_followup_report_invoices_removed(self):
        followup_line = self.create_followup(delay=15)

        invoice = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)

        self.assertPartnerFollowup(self.partner_a, followup_line)

        invoice_attachment = self.env['ir.attachment'].create({
            'name': 'some_attachment.pdf',
            'res_id': invoice.id,
            'res_model': 'account.move',
            'raw': b'test',
            'type': 'binary',
        })
        invoice._message_set_main_attachment_id(invoice_attachment)

        followup_data = self.partner_a._query_followup_data()
        aml_id = followup_data[self.partner_a.id]['aml_id']
        aml = self.env['account.move.line'].browse(aml_id)

        with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': self._get_followup_file_name(), 'file_content': b'', 'file_type': 'pdf'}):
            self.partner_a._execute_followup_partner(options={
                'partner_id': self.partner_a.id,
                'snailmail': False,
                'attachment_ids': [],
                'followup_line': followup_line,
                'aml': aml,
            })

        sent_attachments = self.env['mail.message'].search([('partner_ids', '=', self.partner_a.id)]).attachment_ids
        self.assertEqual(sent_attachments.mapped('name'), [self._get_followup_file_name()])

    def test_manual_followup_report_join_invoices(self):
        followup_line = self.create_followup(delay=15)

        invoice = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)

        self.assertPartnerFollowup(self.partner_a, followup_line)

        invoice_attachment = self.env['ir.attachment'].create({
            'name': 'some_attachment.pdf',
            'res_id': invoice.id,
            'res_model': 'account.move',
            'raw': b'test',
            'type': 'binary',
        })
        invoice._message_set_main_attachment_id(invoice_attachment)

        followup_data = self.partner_a._query_followup_data()
        aml_id = followup_data[self.partner_a.id]['aml_id']
        aml = self.env['account.move.line'].browse(aml_id)

        with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': self._get_followup_file_name(), 'file_content': b'', 'file_type': 'pdf'}):
            self.partner_a._execute_followup_partner(options={
                'partner_id': self.partner_a.id,
                'snailmail': False,
                'attachment_ids': invoice_attachment.ids,
                'followup_line': followup_line,
                'aml': aml,
            })

        sent_attachments = self.env['mail.message'].search([('partner_ids', '=', self.partner_a.id)]).attachment_ids
        self.assertEqual(sent_attachments.mapped('name'), [self._get_followup_file_name()])

    def _prepare_invoices_and_attachments(self):
        invoice_1 = self.init_invoice("out_invoice", amounts=[1000], post=True)
        invoice_2 = self.init_invoice("out_invoice", amounts=[2000], post=True)

        attachment_1 = self.env['ir.attachment'].create({
            'name': 'att_1.pdf',
            'res_id': invoice_1.id,
            'res_model': 'account.move',
            'raw': b'test',
            'type': 'binary',
        })
        invoice_1._message_set_main_attachment_id(attachment_1)

        attachment_2 = self.env['ir.attachment'].create([{
            'name': 'att_2.pdf',
            'res_id': invoice_2.id,
            'res_model': 'account.move',
            'res_field': 'invoice_pdf_report_file',  # simulates send & print
            'raw': b'test',
            'type': 'binary',
        }])

        return invoice_1 + invoice_2, attachment_1 + attachment_2

    def test_auto_followup_invoice_attachments_pdf_report_file(self):
        invoices, attachments = self._prepare_invoices_and_attachments()
        self.create_followup(delay=15)
        with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': self._get_followup_file_name(), 'file_content': b'', 'file_type': 'pdf'}):
            self.partner_a.action_manually_process_automatic_followups()

        sent_attachments = self.env['mail.message'].search([('partner_ids', '=', invoices.partner_id.id)]).attachment_ids
        self.assertEqual(sent_attachments.mapped('name'), [self._get_followup_file_name(), attachments[1].name])

    def test_action_report_followup(self):
        def _run_pdf_engine_without_processing(*args, **kwargs):
            return PDF_RAW

        followup_line = self.create_followup(delay=15)
        self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id, price_unit=200)

        self.assertPartnerFollowup(self.partner_a, followup_line)
        options = {}
        options['followup_line'] = followup_line
        with patch.object(self.env.registry['ir.actions.report'], '_run_pdf_engine_without_processing', _run_pdf_engine_without_processing):
            followup_letter = self.env['ir.actions.report'].with_context(force_report_rendering=True)._render_qweb_pdf('account_followup.report_followup_print_all', self.partner_a.id)[0]
        self.assertTrue(followup_letter)

    def test_automatic_followup_report_attachments_from_template(self):
        mail_template = self.env['mail.template'].create({
            'name': 'reminder',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'email_cc': 'john.carmac@example.me',
        })
        template_attachment = self.env['ir.attachment'].create({
            'name': 'template_attachment.pdf',
            'res_id': mail_template.id,
            'res_model': 'mail.template',
            'raw': b'test',
            'type': 'binary',
        })
        mail_template.attachment_ids = [template_attachment.id]

        dynamic_report = self.env['ir.actions.report'].create({
            'name': 'Test Report Partner',
            'model': 'res.partner',
            'report_name': 'account_followup.report_followup_print_all',
            'print_report_name': "'followup_dynamic_report'",
        })
        mail_template.report_template_ids = [dynamic_report.id]

        followup_line = self.create_followup(delay=15)
        followup_line.mail_template_id = mail_template

        invoice = self._create_invoice_followup(invoice_date='2016-01-01', partner=self.partner_a.id)
        self.assertPartnerFollowup(self.partner_a, followup_line)

        invoice_attachment = self.env['ir.attachment'].create({
            'name': 'invoice_attachment.pdf',
            'res_id': invoice.id,
            'res_model': 'account.move',
            'res_field': 'invoice_pdf_report_file',  # simulates send & print
            'raw': b'test',
            'type': 'binary',
        })
        invoice._message_set_main_attachment_id(invoice_attachment)

        with patch.object(self.env.registry['account.report'], 'export_to_pdf', autospec=True, side_effect=lambda *args, **kwargs: {'file_name': self._get_followup_file_name(), 'file_content': b'', 'file_type': 'pdf'}):
            self.partner_a.action_manually_process_automatic_followups()

        sent_attachments = self.env['mail.message'].search([('partner_ids', '=', self.partner_a.id)]).attachment_ids
        self.assertEqual(sent_attachments.mapped('name'), [self._get_followup_file_name(), 'template_attachment.pdf', 'followup_dynamic_report.html', 'invoice_attachment.pdf'])

    @freeze_time('2025-12-01')
    def test_followup_report_single_foreign_currency(self):
        """
        Test that the followup report displays the total amount in currency
        when all invoices from a partner share the same foreign currency.
        """
        invoice_vals = {
            'move_type': 'out_invoice',
            'invoice_date': '2025-12-01',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 200,
                'tax_ids': [],
            })]
        }
        options = self._generate_options(self.report, '2025-12-01', '2025-12-31')

        # First unpaid invoice in foreign currency.
        self.env['account.move'].create({**invoice_vals, 'currency_id': self.other_currency.id}).action_post()

        # Second unpaid invoice using the same foreign currency.
        self.env['account.move'].create({**invoice_vals, 'currency_id': self.other_currency.id}).action_post()

        # The amount currency total should be displayed.
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                 Amount,    Amount Currency
            [   0,                                   4,         5],
            [
                ('Open Items',                       200.0,     400.0),
                ('partner_a',                        200.0,     400.0),
                ('Total Open Items',                 200.0,     400.0),
            ],
            options,
            currency_map={5: {'currency': self.other_currency}},
        )

        # Third unpaid invoice using the company currency.
        self.env['account.move'].create(invoice_vals).action_post()

        # The amount currency total should no longer be displayed.
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                 Amount,    Amount Currency
            [   0,                                   4,         5],
            [
                ('Open Items',                       400.0,     ''),
                ('partner_a',                        400.0,     ''),
                ('Total Open Items',                 400.0,     ''),
            ],
            options,
        )

        # Last unpaid invoice using the company currency and another partner (partner_b).
        self.env['account.move'].create({**invoice_vals, 'partner_id': self.partner_b.id}).action_post()

        # The 'amount_currency' column should remain empty for 'partner_b', even though
        # there's only one currency (company currency values should not appear in the 'amount_currency' column).
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                 Amount,    Amount Currency
            [   0,                                   4,         5],
            [
                ('Open Items',                       600.0,     ''),
                ('partner_a',                        400.0,     ''),
                ('partner_b',                        200.0,     ''),
                ('Total Open Items',                 600.0,     ''),
            ],
            options,
        )
