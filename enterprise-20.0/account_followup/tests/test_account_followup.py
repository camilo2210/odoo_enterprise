from unittest.mock import patch
from freezegun import freeze_time
from odoo import Command, fields
from odoo.tests import tagged
from odoo.addons.account_followup.tests.common import TestAccountFollowupCommon
from odoo.addons.mail.tests.common import MailCommon
from dateutil.relativedelta import relativedelta


@tagged('post_install', '-at_install')
class TestAccountFollowupReports(TestAccountFollowupCommon, MailCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['account_followup.followup.line'].search([]).unlink()

        wkhtmltopdf_patcher = patch.object(
            cls.env.registry['ir.actions.report'],
            '_run_pdf_engine_without_processing',
            lambda *args, **kwargs: b"0"
        )
        wkhtmltopdf_patcher.start()
        cls.addClassCleanup(wkhtmltopdf_patcher.stop)
        cls.partner_a.email = 'partnera@example.com'

    def test_followup_responsible(self):
        """
        Test that the responsible is correctly set
        """
        self.first_followup_line = self.create_followup(delay=-10)

        user1 = self.env['res.users'].create({
            'name': 'A User',
            'login': 'a_user',
            'email': 'a@user.com',
            'group_ids': [(6, 0, [self.env.ref('account.group_account_user').id])]
        })
        user2 = self.env['res.users'].create({
            'name': 'Another User',
            'login': 'another_user',
            'email': 'another@user.com',
            'group_ids': [(6, 0, [self.env.ref('account.group_account_user').id])]
        })
        # 1- no info, use current user
        self.assertEqual(self.partner_a._get_followup_responsible(), self.env.user)

        # 2- set invoice user
        invoice1 = self._create_invoice_followup(price_unit=2000, invoice_date='2026-01-02', partner=self.partner_a.id, post=False)
        invoice2 = self._create_invoice_followup(price_unit=1000, invoice_date='2026-01-02', partner=self.partner_a.id, post=False)
        invoice1.invoice_user_id = user1
        invoice2.invoice_user_id = user2
        (invoice1 + invoice2).action_post()
        # Should pick invoice_user_id of the most delayed move, with highest residual amount in case of tie (invoice1)
        self.assertEqual(self.partner_a._get_followup_responsible(), user1)
        # If user1 is archived, it shouldn't be selected as responsible
        user1.active = False
        self.assertEqual(self.partner_a._get_followup_responsible(), self.env.user)
        user1.active = True

        with freeze_time('2025-12-23'):
            self._execute_followup(self.partner_a)

        # 4- Modify the default responsible on followup level
        self.partner_a.followup_line_id.activity_default_responsible_type = 'salesperson'
        self.assertEqual(self.partner_a._get_followup_responsible(), user1)
        self.assertEqual(self.partner_a._get_followup_responsible(multiple_responsible=True), (user1 + user2))

        self.partner_a.followup_line_id.activity_default_responsible_type = 'account_manager'
        self.partner_a.user_id = user2
        self.assertEqual(self.partner_a._get_followup_responsible(), self.partner_a.user_id)

    def test_followup_activity(self):
        first_followup_line = self.create_followup(delay=10)
        first_followup_line.create_activity = True
        first_followup_line.activity_default_responsible_type = 'salesperson'
        user1 = self.env['res.users'].create({
            'name': 'A User',
            'login': 'a_user',
            'email': 'a@user.com',
            'group_ids': [Command.set([self.env.ref('account.group_account_user').id])]
        })
        user2 = self.env['res.users'].create({
            'name': 'Another User',
            'login': 'another_user',
            'email': 'another@user.com',
            'group_ids': [Command.set([self.env.ref('account.group_account_user').id])]
        })
        inv1 = self._create_invoice_followup('2022-01-02', partner=self.partner_a.id, post=False)
        inv1.invoice_user_id = user1
        inv2 = self._create_invoice_followup('2022-01-02', partner=self.partner_a.id, post=False)
        inv2.invoice_user_id = user2
        (inv1 + inv2).action_post()

        with freeze_time('2022-01-12'):
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.activity_ids.user_id, (user1 + user2))

    def test_followup_no_invoice_user_id(self):
        first_followup_line = self.create_followup(delay=10)
        first_followup_line.create_activity = True
        first_followup_line.activity_default_responsible_type = 'salesperson'
        inv1 = self._create_invoice_followup('2022-01-02', partner=self.partner_a.id)
        inv1.invoice_user_id = None
        with freeze_time('2022-01-13'):
            self.assertEqual(self.partner_a._get_followup_responsible(), self.user)

    def test_followup_line(self):
        self.first_followup_line = self.create_followup(delay=-10)
        self.second_followup_line = self.create_followup(delay=10)
        self.third_followup_line = self.create_followup(delay=15)

        self._create_invoice_followup('2022-01-15', partner=self.partner_a.id)

        with freeze_time('2022-01-03'):
            # No Reminder should be sent until due_date + delay
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2022-01-05'):
            # For negative delays we remind before the due date
            self.assertPartnerFollowup(self.partner_a, self.first_followup_line)
            self._execute_followup(self.partner_a)
        with freeze_time('2022-01-25'):
            # 10 days after
            self.assertPartnerFollowup(self.partner_a, self.second_followup_line)
            self._execute_followup(self.partner_a)
        with freeze_time('2022-02-02'):
            # 15 days after
            self.assertPartnerFollowup(self.partner_a, self.third_followup_line)
            self._execute_followup(self.partner_a)
        with freeze_time('2022-02-15'):
            self.assertPartnerFollowup(self.partner_a, None)

            # create a new overdue invoice
            self._create_invoice_followup('2022-01-03', partner=self.partner_a.id)
            self.assertPartnerFollowup(self.partner_a, self.first_followup_line)

            aml_ids = self.partner_a.unreconciled_aml_ids

            # Exclude every unreconciled invoice line.
            aml_ids.no_followup = True
            self.assertPartnerFollowup(self.partner_a, None)

            # It resets if we don't exclude them anymore.
            aml_ids.no_followup = False
            self.assertPartnerFollowup(self.partner_a, self.first_followup_line)

            self.env['account.payment.register'].create({
                'line_ids': self.partner_a.unreconciled_aml_ids,
            })._create_payments()
            self.assertPartnerFollowup(self.partner_a, None)

    def test_followup_line_belated(self):
        self.first_followup_line = self.create_followup(delay=-10)
        self.second_followup_line = self.create_followup(delay=10)
        self.third_followup_line = self.create_followup(delay=15)

        self._create_invoice_followup('2022-01-01', partner=self.partner_a.id)

        # invoice belated when sent in a date different than the date that it should have been sent in for any reason
        with freeze_time('2022-01-10'):
            # if invoice is created with 'due_date' in the past or
            # the 'automatic_reminder' was enabled while there is ongoing invoices
            # always rollback to the first reminder
            self.assertPartnerFollowup(self.partner_a, self.first_followup_line)
            self._execute_followup(self.partner_a)

        # when an invoice reminder is belated we use this formula to decide the next when reminder
        # next_delay_value - current_delay_value. in this case '10 -(-10) = 20'
        with freeze_time('2022-01-20'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2022-01-30'):
            self.assertPartnerFollowup(self.partner_a, self.second_followup_line)
            self._execute_followup(self.partner_a)
        with freeze_time('2022-02-5'):
            self.assertPartnerFollowup(self.partner_a, self.third_followup_line)
            self._execute_followup(self.partner_a)

    def test_follow_up_change_due_date(self):
        fl1 = self.create_followup(delay=5)
        fl2 = self.create_followup(delay=10)
        fl3 = self.create_followup(delay=15)
        # invoice get first reminder on time then due_date is changed to be in the future
        inv1 = self._create_invoice_followup('2025-01-01', partner=self.partner_a.id)
        with freeze_time('2025-01-06'):
            self.assertPartnerFollowup(self.partner_a, fl1)
            self._execute_followup(self.partner_a)

        inv1.invoice_date_due = '2025-01-10'
        receivable_lines = inv1.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-01-10'})
        with freeze_time('2025-01-10'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-01-15'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-01-20'):
            self.assertPartnerFollowup(self.partner_a, fl2)

        self.env['account.payment.register'].create({
                'line_ids': inv1.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

        # invoice get first reminder on time then due_date is changed to be in the past (it will be considered belated then)
        inv2 = self._create_invoice_followup('2025-01-15', partner=self.partner_a.id)
        with freeze_time('2025-01-20'):
            self.assertPartnerFollowup(self.partner_a, fl1)
            self._execute_followup(self.partner_a)

        inv2.invoice_date_due = '2025-01-05'
        receivable_lines = inv2.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-01-05'})
        with freeze_time('2025-01-23'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-01-25'):
            self.assertPartnerFollowup(self.partner_a, fl2)
            self._execute_followup(self.partner_a)
        with freeze_time('2025-01-30'):
            self.assertPartnerFollowup(self.partner_a, fl3)

        self.env['account.payment.register'].create({
                'line_ids': inv2.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

        # invoice get first reminder belated then due_ate is changed to be in the future (it will be considered on time)
        inv3 = self._create_invoice_followup('2025-01-01', partner=self.partner_a.id)

        with freeze_time('2025-02-01'):
            self.assertPartnerFollowup(self.partner_a, fl1)
            self._execute_followup(self.partner_a)

        inv3.invoice_date_due = '2025-02-10'
        receivable_lines = inv3.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-02-10'})

        with freeze_time('2025-02-15'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-02-20'):
            self.assertPartnerFollowup(self.partner_a, fl2)

        self.env['account.payment.register'].create({
                'line_ids': inv3.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

        # invoice get first reminder belated then due_ate is changed to be in the past
        inv4 = self._create_invoice_followup('2025-02-01', partner=self.partner_a.id)

        with freeze_time('2025-02-20'):
            self.assertPartnerFollowup(self.partner_a, fl1)
            self._execute_followup(self.partner_a)

        inv4.invoice_date_due = '2025-01-01'
        receivable_lines = inv4.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-01-01'})

        with freeze_time('2025-02-25'):
            self.assertPartnerFollowup(self.partner_a, fl2)
            self._execute_followup(self.partner_a)
        with freeze_time('2025-03-02'):
            self.assertPartnerFollowup(self.partner_a, fl3)

    def test_follow_up_change_due_date_one_invoice(self):
        fl1 = self.create_followup(delay=-10)
        fl2 = self.create_followup(delay=-5)
        fl3 = self.create_followup(delay=5)
        fl4 = self.create_followup(delay=10)
        fl5 = self.create_followup(delay=15)

        # first reminder on time
        inv1 = self._create_invoice_followup('2025-01-15', partner=self.partner_a.id)
        with freeze_time('2025-01-05'):
            self.assertPartnerFollowup(self.partner_a, fl1)
            self._execute_followup(self.partner_a)

        # the due date is moved into the future.
        inv1.invoice_date_due = '2025-01-20'
        receivable_lines = inv1.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-01-20'})

        with freeze_time('2025-01-10'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-01-15'):
            self.assertPartnerFollowup(self.partner_a, fl2)
            self._execute_followup(self.partner_a)

        # The due date is moved into the past, so the invoice is treated as belated.
        inv1.invoice_date_due = '2025-01-10'
        receivable_lines = inv1.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-01-10'})
        # The next reminder is scheduled after (next_delay - current_delay) days.
        # The last automatic reminder was sent on 2025-01-15 with a delay of -5,
        # so the next reminder (delay = 5) should be sent 10 days later, on 2025-01-25.
        with freeze_time('2025-01-20'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-01-25'):
            self.assertPartnerFollowup(self.partner_a, fl3)
            self._execute_followup(self.partner_a)

        # The due_date is moved further into the past. The invoice is still treated as belated.
        inv1.invoice_date_due = '2025-01-01'
        receivable_lines = inv1.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-01-01'})
        # The next reminder is scheduled after (next_delay - current_delay) days.
        # The last automatic reminder was sent on 2025-01-25 with a delay of 5,
        # so the next reminder (delay = 10) should be sent 5 days later, on 2025-01-30.
        with freeze_time('2025-01-23'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-01-30'):
            self.assertPartnerFollowup(self.partner_a, fl4)
            self._execute_followup(self.partner_a)

        # due_date is changed to be in future
        inv1.invoice_date_due = '2025-02-05'
        receivable_lines = inv1.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines.write({'date_maturity': '2025-02-05'})

        # Since fl1, fl2, fl3, and fl4 have already been sent, and the due date was moved into the future
        # the next reminder (fl5) is scheduled 15 days after the new due date (2025-02-05), so it will be sent on 2025-02-20.
        with freeze_time('2025-02-10'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-02-15'):
            self.assertPartnerFollowup(self.partner_a, None)
        with freeze_time('2025-02-20'):
            self.assertPartnerFollowup(self.partner_a, fl5)

    def test_follow_up_older_invoice_while_ongoing_one(self):
        fl1 = self.create_followup(delay=5)
        fl2 = self.create_followup(delay=10)
        fl3 = self.create_followup(delay=15)
        inv1 = self._create_invoice_followup('2025-02-01', partner=self.partner_a.id)

        with freeze_time('2025-02-06'):
            self.assertPartnerFollowup(self.partner_a, fl1, inv1)
            self._execute_followup(self.partner_a)

        inv2 = self._create_invoice_followup('2025-01-01', partner=self.partner_a.id)
        with freeze_time('2025-02-07'):
            self.assertPartnerFollowup(self.partner_a, fl1, inv2)
            self._execute_followup(self.partner_a)
        with freeze_time('2025-02-17'):
            self.assertPartnerFollowup(self.partner_a, fl2, inv2)
            self._execute_followup(self.partner_a)
        with freeze_time('2025-02-22'):
            self.assertPartnerFollowup(self.partner_a, fl3, inv2)
            self._execute_followup(self.partner_a)

        self.env['account.payment.register'].create({
                'line_ids': inv2.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

        with freeze_time('2025-02-18'):
            self.assertPartnerFollowup(self.partner_a, fl2, inv1)
            self._execute_followup(self.partner_a)

    def test_followup_multiple_invoices(self):
        followup_10 = self.create_followup(delay=10)
        followup_15 = self.create_followup(delay=15)
        followup_30 = self.create_followup(delay=30)

        inv1 = self._create_invoice_followup('2022-01-01', partner=self.partner_a.id)
        self._create_invoice_followup('2022-01-02', partner=self.partner_a.id)

        # 9 days overdue → No followup level yet
        with freeze_time('2022-01-10'):
            self.assertPartnerFollowup(self.partner_a, None)

        # 10 days overdue → first reminder level (first invoice)
        with freeze_time('2022-01-11'):
            self.assertPartnerFollowup(self.partner_a, followup_10)
            # execute reminder
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_10)
            self.assertEqual(self.partner_a.last_reminder, fields.Date.today())
            # next eligible level should be followup_15 (but not yet triggered)
            self.assertPartnerFollowup(self.partner_a, None)

        # 15 days overdue → second reminder level (first invoice)
        with freeze_time('2022-01-16'):
            self.assertPartnerFollowup(self.partner_a, followup_15)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_15)
            self.assertEqual(self.partner_a.last_reminder, fields.Date.today())
            # next eligible level followup_30, but not yet triggered
            self.assertPartnerFollowup(self.partner_a, None)

        # 30 days overdue → third reminder level (first invoice)
        with freeze_time('2022-01-31'):
            self.assertPartnerFollowup(self.partner_a, followup_30)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_30)
            self.assertEqual(self.partner_a.last_reminder, fields.Date.today())
            ## reconcile first invoice
            self.env['account.payment.register'].create({
                'line_ids': inv1.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

        # we send the first reminder, since this invoice has never received a reminder
        # 10 days overdue → first reminder level (second invoice)
        with freeze_time('2022-02-01'):
            self.assertPartnerFollowup(self.partner_a, followup_10)
            self._execute_followup(self.partner_a)

    def test_partner_multiple_invoice_reminder_on_same_day(self):
        followup_10 = self.create_followup(delay=10)
        followup_15 = self.create_followup(delay=15)

        inv1 = self._create_invoice_followup('2022-01-01', partner=self.partner_a.id)
        self._create_invoice_followup('2022-01-01', partner=self.partner_a.id)

        # first invoice
        with freeze_time('2022-01-11'):
            self.assertPartnerFollowup(self.partner_a, followup_10)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_10)
        # first invoice
        with freeze_time('2022-01-16'):
            self.assertPartnerFollowup(self.partner_a, followup_15)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_15)
            ## pay first invoice
            self.env['account.payment.register'].create({
                'line_ids': inv1.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()
        # second invoice
        with freeze_time('2022-01-17'):
            self.assertPartnerFollowup(self.partner_a, followup_10)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_10)
        # second invoice
        with freeze_time('2022-01-22'):
            self.assertPartnerFollowup(self.partner_a, followup_15)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_15)

    def test_followup_status_entry_lines(self):
        """
            Creating an entry should not affect the followups as there is no concept of due date with this flow.
        """
        self.followup_line = self.create_followup(delay=10)

        with freeze_time('2022-01-02'):
            invoice = self.env['account.move'].create({
                'move_type': 'entry',
                'date': fields.Date.from_string('2022-01-02'),
                'partner_id': self.partner_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'name': 'line1',
                        'account_id': self.company_data['default_account_revenue'].id,
                        'debit': 500.0,
                        'credit': 0.0,
                    }),
                    Command.create({
                        'name': 'counterpart line',
                        'account_id': self.company_data['default_account_receivable'].id,
                        'debit': 0.0,
                        'credit': 500.0,
                    })
                ]
            })
            invoice.action_post()

        with freeze_time('2022-01-13'):
            self.assertPartnerFollowup(self.partner_a, None)

    def test_followup_status_residual(self):
        """
            Payments for partially paid invoices should contribute their residual to the due amount.
            This is required because the paid invoice's receivable line is reconciled, and thus is
            not considered in the query calculating followup_status.
        """

        self.followup_line = self.create_followup(delay=10)

        with freeze_time('2022-01-02'):
            invoice_1 = self._create_invoice_followup('2022-01-02', partner=self.partner_a.id)
            self._create_invoice_followup('2022-01-02', partner=self.partner_a.id)

            misc_payment_1 = self.env['account.move'].create({
                'move_type': 'entry',
                'date': fields.Date.from_string('2022-01-02'),
                'partner_id': self.partner_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'name': 'line1',
                        'account_id': self.company_data['default_account_revenue'].id,
                        'debit': 600.0,
                        'credit': 0.0,
                    }),
                    Command.create({
                        'name': 'counterpart line',
                        'account_id': self.company_data['default_account_receivable'].id,
                        'debit': 0.0,
                        'credit': 600.0,
                    })
                ]
            })
            misc_payment_1.action_post()

            (invoice_1 + misc_payment_1).line_ids.filtered(lambda l: l.account_type == 'asset_receivable').reconcile()

        with freeze_time('2022-01-13'):
            self.assertPartnerFollowup(self.partner_a, self.followup_line)

    def test_followup_contacts(self):
        followup_contacts = self.partner_a._get_all_followup_contacts()
        billing_contact = self.env['res.partner'].browse(self.partner_a.address_get(['invoice'])['invoice'])
        self.assertEqual(billing_contact, followup_contacts)

    def test_followup_cron(self):
        cron = self.env.ref('account_followup.ir_cron_follow_up')
        self.company.automatic_invoice_reminder = True
        followup_10 = self.create_followup(delay=10)
        self._create_invoice_followup('2022-01-01', partner=self.partner_a.id)

        # Check that no followup is automatically done if there is no action needed
        with (
            freeze_time('2022-01-10'),
            patch.object(self.env.registry['res.partner'], '_send_followup') as patched,
            self.enter_registry_test_mode(),
        ):
            self.assertPartnerFollowup(self.partner_a, None)
            cron.method_direct_trigger()
            patched.assert_not_called()
            self.assertPartnerFollowup(self.partner_a, None)

        # Check that the action is taken one and only one time when there is an action needed
        with (
            freeze_time('2022-01-11'),
            patch.object(self.env.registry['res.partner'], '_send_followup') as patched,
            self.enter_registry_test_mode(),
        ):
            self.assertPartnerFollowup(self.partner_a, followup_10)
            cron.method_direct_trigger()
            patched.assert_called_once()
            self.assertPartnerFollowup(self.partner_a, None)

    def test_onchange_residual_amount(self):
        '''
        Test residual onchange on account move lines: the residual amount is
        computed using an sql query. This test makes sure the computation also
        works properly during onchange (on records having a NewId).
        '''
        invoice = self._create_invoice_followup('2016-01-01', partner=self.partner_a.id)
        self._create_invoice_followup('2016-01-02', partner=self.partner_a.id)

        self.env['account.payment.register'].with_context(active_ids=invoice.ids, active_model='account.move').create({
            'payment_date': invoice.date,
            'amount': 100,
        })._create_payments()

        self.assertRecordValues(self.partner_a, [{'total_due': 900.0}])
        self.assertRecordValues(self.partner_a.unreconciled_aml_ids.sorted(), [
            {'amount_residual_currency': 500.0},
            {'amount_residual_currency': 400.0},
        ])

        self.assertRecordValues(self.partner_a.unreconciled_aml_ids.sorted(), [
            {'amount_residual_currency': 500.0},
            {'amount_residual_currency': 400.0},
        ])

    def test_compute_total_due(self):
        self._create_invoice_followup('2016-01-01', partner=self.partner_a.id)
        self._create_invoice_followup('2017-01-01', partner=self.partner_a.id)
        self._create_invoice_followup(fields.Date.today() + relativedelta(months=1), partner=self.partner_a.id)
        self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'invoice_date': date,
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500,
                'tax_ids': [],
            })]
        } for date in ('2016-01-01', '2017-01-01', fields.Date.today() + relativedelta(months=1))]).action_post()

        self.assertRecordValues(self.partner_a, [{
            'total_due': 1500.0,
            'total_overdue': 1000.0,
            'total_all_due': 0.0,
            'total_all_overdue': 0.0,
        }])

    def test_followup_copy_data(self):
        """
        Test followup report by:
        - Duplicating a single record with no default
        - Duplicating several records at the same time
        """
        followup_50 = self.create_followup(delay=50)
        followup_60 = self.create_followup(delay=60)

        # Duplicate single record with no default values
        followup_50_duplicate = followup_50.copy()
        self.assertTrue(followup_50_duplicate)
        self.assertEqual(followup_50_duplicate.delay, 75)

        # Duplicate multiple records at the same time with no default values
        multiple_followup_records = followup_50 + followup_60
        multiple_followup_records_duplicate = multiple_followup_records.copy()
        self.assertTrue(multiple_followup_records_duplicate)
        self.assertEqual(multiple_followup_records_duplicate[0].delay, 90)
        self.assertEqual(multiple_followup_records_duplicate[1].delay, 105)

    def test_followup_template_recipients_with_cron(self):
        """
        tests that when a mail_cc is defined on a template,
        even if the action is ran from a cron (and de facto from `res.partner.send_followup_email`)
        the email is correctly sent
        Completes `test_manual_reminder_get_template_mail_addresses`
        """
        self.partner_a.email = "test@test.com"
        mail_cc = self.env['res.partner'].create({
            'name': 'John Carmac',
            'email': 'john.carmac@example.me',
        })
        mail_template = self.env['mail.template'].create({
            'name': 'reminder',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'email_cc': mail_cc.email,
            'use_default_to': False,
        })
        followup_10 = self.create_followup(delay=10)
        followup_10.mail_template_id = mail_template
        self._create_invoice_followup('2025-05-01', partner=self.partner_a.id)

        with freeze_time('2025-05-12'), self.mock_mail_gateway(mail_unlink_sent=False):
            options = {
                'followup_line': followup_10,
                'partner_id': self.partner_a.id,
            }
            self.partner_a.send_followup_email(options=options)
        self.assertMailMail(mail_cc, 'sent', author=self.env.user.partner_id)

    def test_partner_followup_level(self):
        """Check that the partner followup level is updated to the lowest eligible reminder."""
        followup_7 = self.create_followup(delay=7)
        followup_15 = self.create_followup(delay=15)

        self._create_invoice_followup('2026-02-01', partner=self.partner_a.id)

        # 7 days overdue → first reminder level (first invoice)
        with freeze_time('2026-02-08'):
            self.assertPartnerFollowup(self.partner_a, followup_7)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_7)
        # 15 days overdue → second reminder level (first invoice)
        with freeze_time('2026-02-16'):
            self.assertPartnerFollowup(self.partner_a, followup_15)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_15)

        invoice_2 = self._create_invoice_followup('2026-01-01', partner=self.partner_a.id)
        # 7 days overdue → first reminder level (second invoice)
        with freeze_time('2026-02-17'):
            self.assertPartnerFollowup(self.partner_a, followup_7)
            self._execute_followup(self.partner_a)
            self.assertEqual(self.partner_a.followup_line_id, followup_7)

        # Excluding the first invoice from followup should change partner Reminder levels
        invoice_2.line_ids.no_followup = True
        self.assertEqual(self.partner_a.followup_line_id, followup_15)

    def test_has_moves_without_invoice(self):
        """
        Test that has_moves is True for a partner referenced
        only at account.move.line level (no partner at move level)
        """
        partner = self.env['res.partner'].create({'name': 'Test Partner'})
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'line_ids': [
                Command.create({
                    'partner_id': partner.id,
                    'account_id': self.company_data['default_account_receivable'].id,
                    'debit': 100.0,
                    'credit': 0.0,
                }),
                Command.create({
                    'account_id': self.company_data['default_account_revenue'].id,
                    'debit': 0.0,
                    'credit': 100.0,
                }),
            ],
        })
        move.action_post()
        self.assertTrue(partner.has_moves)

    def test_search_followup_line_id(self):
        followup_10 = self.create_followup(delay=10)
        followup_20 = self.create_followup(delay=20)
        self._create_invoice_followup('2026-01-01', partner=self.partner_a.id)

        with freeze_time('2026-01-12'):
            self._execute_followup(self.partner_a)

            partners = self.env['res.partner'].search([('followup_line_id', 'in', followup_10.ids)])
            self.assertIn(self.partner_a, partners)

            partners = self.env['res.partner'].search([('followup_line_id', 'in', followup_20.ids)])
            self.assertNotIn(self.partner_a, partners)

        with freeze_time('2026-01-22'):
            self._execute_followup(self.partner_a)

            partners = self.env['res.partner'].search([('followup_line_id', 'in', followup_10.ids)])
            self.assertNotIn(self.partner_a, partners)

            partners = self.env['res.partner'].search([('followup_line_id', 'in', followup_20.ids)])
            self.assertIn(self.partner_a, partners)

            partners = self.env['res.partner'].search([('followup_line_id', 'in', [])])
            self.assertNotIn(self.partner_a, partners)
