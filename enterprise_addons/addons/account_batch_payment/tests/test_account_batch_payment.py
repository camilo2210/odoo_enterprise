import time
from unittest.mock import patch

from odoo import Command
from odoo.addons.account_accountant.tests.common import TestBankRecWidgetCommon
from odoo.tests import Form, tagged
from odoo.exceptions import RedirectWarning, UserError, ValidationError

@tagged('post_install', '-at_install')
class TestAccountBatchPayment(TestBankRecWidgetCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.other_currency = cls.setup_other_currency('EUR')
        cls.other_currency_2 = cls.setup_other_currency('CHF')

        cls.payment_debit_account_id = cls.copy_account(cls.inbound_payment_method_line.payment_account_id)
        cls.payment_credit_account_id = cls.copy_account(cls.outbound_payment_method_line.payment_account_id)

        cls.journal = cls.company_data['default_journal_bank']
        cls.batch_deposit_method = cls.env.ref('account_batch_payment.account_payment_method_batch_deposit')
        cls.batch_deposit = cls.journal.inbound_payment_method_line_ids.filtered(lambda l: l.code == 'batch_payment')

        cls.partner_bank_account = cls.env['res.partner.bank'].create({
            'account_number': 'BE32707171912447',
            'partner_id': cls.partner_a.id,
            'allow_out_payment': True,
        })

    @classmethod
    def create_payment(cls, partner, amount, **kwargs):
        """ Create a batch deposit payment """
        payment = cls.env['account.payment'].create({
            'journal_id': cls.journal.id,
            'payment_type': 'inbound',
            'date': time.strftime('%Y') + '-07-15',
            'amount': amount,
            'partner_id': partner.id,
            'partner_type': 'customer',
            **kwargs,
        })
        payment.action_post()
        return payment

    def _create_multi_company_payments_and_context(self, companies_dict, add_company_context=None):
        payments = self.env['account.payment']
        companies_context = self.env['res.company']
        field_record = self.env['ir.model.fields']._get('res.partner', 'property_account_receivable_id')
        property_account_receivable = self.env['ir.default'].search(
            [('field_id', '=', field_record.id), ('company_id', '=', self.company_data['company'].id)], limit=1
        )

        for company, create_property_account_receivable in companies_dict.items():
            if create_property_account_receivable:
                # needed for computation of payment.destination_account_id
                property_account_receivable.copy({'company_id': company.id})
            payment = self.env['account.payment'].with_company(company).create({
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.partner_a.id,
            })
            payment.action_post()
            payments += payment
            companies_context += company

        if add_company_context:
            companies_context += add_company_context

        context = {
            **self.env.context,
            'allowed_company_ids': companies_context.ids,
            'active_ids': payments.ids,
            'active_model': 'account.payment',
        }

        return payments, context

    def test_create_batch_payment_from_payment(self):
        payments = self.env['account.payment']
        for _i in range(2):
            payments += self.env['account.payment'].create({
                'amount': 100.0,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'destination_account_id': self.partner_a.property_account_payable_id.id,
                'currency_id': self.other_currency.id,
                'partner_bank_id': self.partner_bank_account.id,
            })

        payments.action_post()
        batch_payment_action = payments.create_batch_payment()
        batch_payment_id = self.env['account.batch.payment'].browse(batch_payment_action.get('res_id'))
        self.assertEqual(len(batch_payment_id.payment_ids), 2)

    def test_change_payment_state(self):
        """
        Check if the amount is well computed when we change a payment state
        """
        payments = self.env['account.payment']
        for _ in range(2):
            payments += self.env['account.payment'].create({
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'destination_account_id': self.partner_a.property_account_payable_id.id,
                'partner_bank_id': self.partner_bank_account.id,
            })
        payments.action_post()

        batch_payment = self.env['account.batch.payment'].create(
            {
                'journal_id': payments.journal_id.id,
                'payment_method_id': payments.payment_method_id.id,
                'payment_ids': [
                    (6, 0, payments.ids)
                ],
            }
        )

        self.assertRecordValues(batch_payment, [{
            'amount': 200.0,
            'amount_residual': 200.0,
            'amount_residual_currency': 200.0,
        }])

        payments[0].move_id.button_draft()

        # Check that we still keep it
        self.assertRecordValues(batch_payment, [{
            'amount': 200.0,
            'amount_residual': 200.0,
            'amount_residual_currency': 200.0,
        }])

    def test_validate_batch(self):
        """
        Check that we can only validate a batch if all the payments are in progress
        """
        payments = self.env['account.payment']
        for _ in range(2):
            payments += self.env['account.payment'].create({
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'destination_account_id': self.partner_a.property_account_payable_id.id,
                'partner_bank_id': self.partner_bank_account.id,
            })
        payments.action_post()

        batch_payment = self.env['account.batch.payment'].create(
            {
                'journal_id': payments.journal_id.id,
                'payment_method_id': payments.payment_method_id.id,
                'payment_ids': [Command.set(payments.ids)]
            }
        )
        payments[0].action_validate()

        # In accounting, we can only validate a batch if all the payments are paid
        # While in enterprise invoicing, we can validate a batch even if some payments are paid
        is_accounting_installed = self.env['account.move']._get_invoice_in_payment_state() == 'in_payment'
        if is_accounting_installed:
            with self.assertRaisesRegex(RedirectWarning, "To validate the batch, payments must be paid"):
                batch_payment.validate_batch()
            # Set payment to paid state
            payments[0].action_draft()
            payments[0].action_post()
        action = batch_payment.validate_batch()
        self.assertFalse(action)

    def test_batch_payment_sub_company(self):
        """Test the creation of a batch payment from a sub company"""
        self.company_data['company'].write({'child_ids': [Command.create({'name': 'Good Company'})]})
        child_comp = self.company_data['company'].child_ids[0]

        payment, context = self._create_multi_company_payments_and_context({child_comp: True})

        batch = self.env['account.batch.payment'].with_context(context).create({
            'journal_id': payment.journal_id.id,
        })
        self.assertTrue(batch)

    def test_batch_payment_branches(self):
        """
        Test the creation of a batch payment with branches. When all payments are branches of
        a common head office, a batch payment should be allowed to be created.
        """
        main_company = self.company_data['company']
        main_company.vat = '123'
        branch_1 = self.env['res.company'].create({'name': "Branch 1", 'parent_id': main_company.id})
        branch_2 = self.env['res.company'].create({'name': "Branch 2", 'parent_id': main_company.id, 'vat': '456'})
        branch_2_1 = self.env['res.company'].create({'name': "Branch 2 sub-branch 1", 'parent_id': branch_2.id})

        payments, context = self._create_multi_company_payments_and_context({branch_1: True, branch_2: True, branch_2_1: True})

        batch = self.env['account.batch.payment'].with_context(context).create({
            'journal_id': payments[0].journal_id.id,
            'payment_ids': payments.ids,
        })
        self.assertTrue(batch)

    def test_batch_payment_different_companies(self):
        """ Payments from different companies not belonging to the same head company should raise an error. """
        main_company = self.company_data['company']
        company_b = self.setup_other_company()['company']

        payments, context = self._create_multi_company_payments_and_context({main_company: False, company_b: False}, main_company)

        with self.assertRaisesRegex(ValidationError, "The journal of the batch payment and of the payments it contains must be the same."):
            self.env['account.batch.payment'].with_context(context).create({
                'journal_id': payments[0].journal_id.id,
                'payment_ids': payments.ids,
            })

    def test_batch_payment_foreign_currency(self):
        """
        Make sure that payments in foreign currency are converted for the total amount to be displayed
            currency rate = 1$:10€
            amount_company_currency = 100$
            amount_foreign_currency = 100€ -> 10$
            => batch.amount = 110$
        """
        payments = self.env['account.payment']
        company_currency = self.env.company.currency_id
        foreign_currency = self.other_currency

        self.env['res.currency.rate'].create({
            'name': '2024-05-13',
            'rate': 10,
            'currency_id': foreign_currency.id,
            'company_id': self.env.company.id,
        })

        for currency in (company_currency, foreign_currency):
            payments += self.env['account.payment'].create({
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'currency_id': currency.id,
                'date': '2024-05-14',
            })

        payments.action_post()
        batch_payment_action = payments.create_batch_payment()
        batch_payment = self.env['account.batch.payment'].browse(batch_payment_action.get('res_id'))
        self.assertRecordValues(batch_payment, [{
            'amount': 110.0,
            'amount_residual': 110.0,
            'amount_residual_currency': 110.0,
        }])

    def test_batch_payment_move_different_currencies(self):
        """
        Make sure that payments linked to a move in foreign currency 1 are converted correctly when
        the batch is in foreign currency 2
        """
        payments = self.env['account.payment']
        bank_journal_2 = self.company_data['default_journal_bank'].copy({'currency_id': self.other_currency_2.id})

        outstanding_payment_B = self.inbound_payment_method_line.payment_account_id.copy()
        bank_journal_2.inbound_payment_method_line_ids.payment_account_id = outstanding_payment_B

        for currency, rate in [(self.other_currency, 10), (self.other_currency_2, 20)]:
            self.env['res.currency.rate'].create({
                'name': '2024-05-13',
                'rate': rate,
                'currency_id': currency.id,
                'company_id': self.env.company.id,
            })

        for amount in (100.0, 15.0):
            payments += self.env['account.payment'].create({
                'amount': amount,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'currency_id': self.other_currency.id,
                'journal_id': bank_journal_2.id,
                'date': '2024-05-14',
            })

        payments.action_post()
        batch_payment_action = payments.create_batch_payment()
        batch_payment = self.env['account.batch.payment'].browse(batch_payment_action.get('res_id'))
        self.assertRecordValues(batch_payment, [{
            'amount': 230.0,
            'amount_residual': 11.5,
            'amount_residual_currency': 230.0,
        }])

    def test_foreign_currency_batch_payment(self):
        """
        Make sure that payments in company_currency are converted when the batch is in
        foreign currency
        """
        payments = self.env['account.payment']
        foreign_currency = self.other_currency

        bank_journal_2 = self.company_data['default_journal_bank'].copy()

        self.env['res.currency.rate'].create({
            'name': '2024-05-13',
            'rate': 10,
            'currency_id': foreign_currency.id,
            'company_id': self.env.company.id,
        })

        for amount in (100, 15):
            payments += self.env['account.payment'].create({
                'amount': amount,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'currency_id': self.other_currency.id,
                'date': '2024-05-14',
                'journal_id': bank_journal_2.id,
            })

        payments.action_post()
        batch_payment_action = payments.create_batch_payment()
        batch_payment = self.env['account.batch.payment'].browse(batch_payment_action.get('res_id'))
        self.assertRecordValues(batch_payment, [{
            'amount': 11.5,
            'amount_residual': 11.5,
            'amount_residual_currency': 11.5,
        }])

    def test_batch_payment_journal_foreign_currency(self):
        """
        Test that, if a bank journal is set in a foreign currency, the batch payment will be correctly converted
        currency rate = 1$:10€
        payment of 100€ -> 100☺
        payment of 100$ -> 1000☺
        Total -> 1100
        """
        payments = self.env['account.payment']
        company_currency = self.env.company.currency_id
        foreign_currency = self.other_currency

        self.env['res.currency.rate'].create({
            'name': '2024-05-13',
            'rate': 10,
            'currency_id': foreign_currency.id,
            'company_id': self.env.company.id,
        })
        bank_journal_foreign = self.env['account.journal'].create({
            'name': 'Bank2',
            'type': 'bank',
            'code': 'BNK2',
            'currency_id': foreign_currency.id,
        })

        for currency in (company_currency, foreign_currency):
            payments += self.env['account.payment'].create({
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'currency_id': currency.id,
                'date': '2024-05-14',
                'journal_id': bank_journal_foreign.id
            })

        payments.action_post()
        batch_payment_action = payments.create_batch_payment()
        batch_payment = self.env['account.batch.payment'].browse(batch_payment_action.get('res_id'))
        self.assertRecordValues(batch_payment, [{
            'amount': 1100.0,
            'amount_residual': 110.0,
            'amount_residual_currency': 1100.0,
        }])

    def test_create_batch_from_payment_already_in_batch(self):
        payment = self.env['account.payment'].create({
            'amount': 100.0,
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_a.id,
            'destination_account_id': self.partner_a.property_account_payable_id.id,
            'currency_id': self.other_currency.id,
            'partner_bank_id': self.partner_bank_account.id,
        })
        payment.action_post()
        batch_payment_action = payment.create_batch_payment()
        batch_payment_id = self.env['account.batch.payment'].browse(batch_payment_action.get('res_id'))
        batch_payment_id.validate_batch()
        with self.assertRaises(ValidationError):
            payment.create_batch_payment()

    def test_amount_in_paid_state(self):
        """
            Verify that the batch payment amount is correctly computed when the payment state is 'reconciled'.
        """
        payments = self.env['account.payment']

        # Create two inbound payments of 100€ each
        for _ in range(2):
            payments += self.env['account.payment'].create({
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'destination_account_id': self.partner_a.property_account_payable_id.id,
                'partner_bank_id': self.partner_bank_account.id,
            })
        # Post the payments to validate them
        payments.action_post()

        # Update payment states to 'reconciled'
        payments.write({'state': 'reconciled'})

        # Ensure all payments are now in the 'reconciled' state
        self.assertTrue(all(payment.state == 'reconciled' for payment in payments), "Payments should be in 'reconciled' state")

        # Create a batch payment including the two payments
        batch_payment = self.env['account.batch.payment'].create(
            {
                'journal_id': payments.journal_id.id,
                'payment_method_id': payments.payment_method_id.id,
                'payment_ids': [Command.set(payments.ids)],
            }
        )

        # Ensure the amount remains correct after recomputation
        # When accountant is not installed, payments with reconciled state
        # should be counted when recomputing amount_residual
        if self.env['ir.module.module']._get('accountant').state == 'installed':
            self.assertEqual(batch_payment.amount_residual, 0)
            self.assertEqual(batch_payment.amount_residual_currency, 0)
        else:
            self.assertEqual(batch_payment.amount_residual, 200)
            self.assertEqual(batch_payment.amount_residual_currency, 200)
        self.assertEqual(batch_payment.amount, 200)

    def test_zero_amount_payment(self):
        zero_payment = self.create_payment(self.partner_a, 0, payment_method_line_id=self.batch_deposit.id)
        batch_vals = {
            'journal_id': self.journal.id,
            'payment_ids': [(4, zero_payment.id, None)],
            'payment_method_id': self.batch_deposit_method.id,
        }
        self.assertRaises(ValidationError, self.env['account.batch.payment'].create, batch_vals)

    def test_exchange_diff_batch_payment(self):
        """
            This test will do a basic case where the company is in US Dollars but the st_line and the payment are in
            another currencies. Between the moment where we created the batch payment and the st_line a difference of
            rates happens and so an exchange diff is created.
        """
        self.other_currency = self.setup_other_currency('EUR', rates=[('2016-01-03', 2.0), ('2017-01-03', 1.0)])
        payment = self.create_payment(
            partner=self.partner_a,
            amount=100,
            date='2017-01-02',
            journal_id=self.company_data['default_journal_bank'].id,
            currency_id=self.other_currency.id,
        )
        payment.create_batch_payment()

        st_line = self._create_st_line(
            100.0,
            date='2017-01-05',
        )
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {
                'account_id': st_line.journal_id.default_account_id.id,
                'amount_currency': 100.0,
                'currency_id': self.company_data['currency'].id,
                'balance': 100.0,
                'reconciled': False,
            },
            {
                'account_id': payment.outstanding_account_id.id,
                'amount_currency': -100.0,
                'currency_id': self.other_currency.id,
                'balance': -100.0,
                'reconciled': True,
            },
        ])
        exchange_move = st_line.line_ids[1].matched_debit_ids.exchange_move_id
        self.assertRecordValues(exchange_move.line_ids, [
            {
                'account_id': payment.outstanding_account_id.id,
                'currency_id': self.other_currency.id,
                'balance': 50.0,
            },
            {
                'account_id': self.env.company.income_currency_exchange_account_id.id,
                'currency_id': self.other_currency.id,
                'balance': -50.0,
            },
        ])

    def test_partner_account_batch_payments_with_journal_entry(self):
        """ Test the account for batch payments with a linked journal entry """
        for payment_type, account_a, account_b in [
            ('inbound', self.partner_a.property_account_receivable_id, self.partner_b.property_account_receivable_id),
            ('outbound', self.partner_a.property_account_payable_id, self.partner_b.property_account_payable_id),
        ]:
            outstanding_account = self.env['account.payment']._get_outstanding_account(payment_type)
            self.batch_deposit.payment_account_id = outstanding_account
            payment_1 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 100.0,
            })
            payment_2 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_b.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 200.0,
            })
            payments = payment_1 + payment_2
            payments.action_post()
            batch = self.env['account.batch.payment'].create({
                'batch_type': payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payments.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
            batch.validate_batch()
            st_line_amount = 300.0 if payment_type == 'inbound' else -300.0
            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': self.journal.id,
                'amount': st_line_amount,
                'date': '2015-01-01',
                'payment_ref': batch.name,
            })
            st_line.set_batch_payment_bank_statement_line(batch.id)
            bank_account = self.journal.default_account_id
            if payment_type == 'inbound':
                self.assertRecordValues(payments.move_id.line_ids.sorted('balance'), [
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': 300.0},
                ])
            else:
                self.assertRecordValues(payments.move_id.line_ids.sorted('balance'), [
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': -300.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': outstanding_account.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])

    def test_bank_rec_widget_batch_payment_with_entries(self):
        payment = self.create_payment(self.partner_a, 100, journal_id=self.company_data['default_journal_bank'].id)
        payment.create_batch_payment()

        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'name': st_line.payment_ref, 'amount_currency': 100.0, 'currency_id': self.company_data['currency'].id, 'balance': 100.0, 'reconciled': False},
            {'account_id': payment.journal_id.inbound_payment_method_line_ids.payment_account_id.id, 'name': payment.journal_id.inbound_payment_method_line_ids[0].name, 'amount_currency': -100.0, 'currency_id': self.company_data['currency'].id, 'balance': -100.0, 'reconciled': True},
        ])
        self.assertEqual(st_line.line_ids.reconciled_lines_ids, payment.move_id.line_ids.filtered(lambda x: x.account_id.account_type == 'asset_current'))

    def test_bank_rec_widget_batch_payment_delete_payment(self):
        payment = self.create_payment(self.partner_a, 100, payment_method_line_id=self.batch_deposit.id)
        payment.create_batch_payment()

        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)

        # When removing the payment line, the payment should go back to paid but the batch remains untouched
        st_line.delete_reconciled_line(st_line.line_ids[-1].id)
        self.assertEqual(payment.state, 'paid')

    def test_unreconcile_keeps_invoice_posted_when_post_is_blocked(self):
        """ Ensure that unreconciling a batch payment from a bank statement line keeps
        the linked invoice posted even if the internal repost is blocked by a
        third-party module (ex: Studio Approval).
        """
        invoice = self._create_invoice_one_line(price_unit=100, post=True)
        payment = self.create_payment(
            self.partner_a,
            invoice.amount_total,
            payment_method_line_id=self.batch_deposit.id,
            invoice_ids=[Command.set(invoice.ids)],
        )
        payment.create_batch_payment()
        st_line = self._create_st_line(amount=invoice.amount_total)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)

        # Simulate an approval rule that silently rejects action_post
        AccountMove = self.env.registry['account.move']
        original_action_post = AccountMove.action_post

        def gated_action_post(records, *args, **kwargs):
            if records.env.su:
                return original_action_post(records, *args, **kwargs)
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {}}

        with patch.object(AccountMove, 'action_post', gated_action_post):
            st_line.delete_reconciled_line(st_line.line_ids[-1].id)

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(payment.state, 'paid')

    def test_unreconcile_sepa_ct_batch_with_pending_online_status(self):
        """ Ensure that delete_reconciled_line does not raise error when un-reconciling
        a SEPA CT batch payment whose payment_online_status = 'pending'.
        """
        if self.env['ir.module.module']._get('account_online_payment').state != 'installed':
            self.skipTest("account_online_payment not installed")

        # Create a bank account for the company and a SEPA CT journal
        company_bank = self.env['res.partner.bank'].create({
            'partner_id': self.company_data['company'].partner_id.id,
            'account_number': 'BE48363523682327',
        })
        sepa_journal = self.env['account.journal'].create({
            'name': 'SEPA CT Test',
            'type': 'bank',
            'code': 'SEPA',
            'bank_account_id': company_bank.id,
            'currency_id': self.other_currency.id,
        })
        sepa_ct_method = sepa_journal.outbound_payment_method_line_ids.filtered(
            lambda l: l.code == 'sepa_ct'
        )

        invoice = self._create_invoice_one_line(
            move_type='in_invoice',
            currency_id=self.other_currency.id,
            price_unit=100.0,
            post=True,
        )

        payment = self.env['account.payment'].create({
            'journal_id': sepa_journal.id,
            'currency_id': self.other_currency.id,
            'payment_method_line_id': sepa_ct_method.id,
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_a.id,
            'partner_bank_id': self.partner_bank_account.id,
            'amount': invoice.amount_total,
            'invoice_ids': [Command.set(invoice.ids)],
        })
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': sepa_journal.id,
            'payment_ids': [Command.set(payment.ids)],
            'payment_method_id': self.env.ref('account_iso20022.account_payment_method_sepa_ct').id,
            'batch_type': 'outbound',
        })
        # Simulate the batch being sent to the bank online.
        batch.payment_online_status = 'pending'

        st_line = self._create_st_line(amount=-payment.amount, journal_id=sepa_journal.id, partner_id=False)
        st_line.set_batch_payment_bank_statement_line(batch.id)

        st_line.delete_reconciled_line(st_line.line_ids[-1].id)

        self.assertEqual(payment.state, 'paid')
        self.assertEqual(invoice.state, 'posted')

    def test_batch_reconciliation_multiple_installments_payment_term(self):
        """ Test reconciliation of payments for multiple installments payment term lines """
        payment_term = self.env['account.payment.term'].create({
            'name': "20-80_payment_term",
            'company_id': self.company_data['company'].id,
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 20, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 80, 'nb_days': 20}),
            ],
        })
        invoice = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[1000.0])
        invoice.invoice_payment_term_id = payment_term
        invoice.action_post()
        # register payment for the first installment
        payment_1 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 200.0,
            'payment_date': '2015-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payment_1.create_batch_payment()
        st_line_1 = self._create_st_line(amount=200.0, date='2015-01-01', partner_id=False)
        st_line_1.set_batch_payment_bank_statement_line(payment_1.batch_payment_id.id)

        self.assertRecordValues(st_line_1.move_id.line_ids.sorted('balance'), [
            {'balance': -200.0},
            {'balance': 200.0},
        ])

        # register payment for the second installment
        payment_2 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 800.0,
            'payment_date': '2015-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payment_2.create_batch_payment()
        st_line_2 = self._create_st_line(amount=800.0, date='2015-01-01', partner_id=False)
        st_line_2.set_batch_payment_bank_statement_line(payment_2.batch_payment_id.id)

        self.assertRecordValues(st_line_2.move_id.line_ids.sorted('balance'), [
            {'balance': -800.0},
            {'balance': 800.0},
        ])
        self.assertRecordValues(invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term').sorted('balance'), [
            {'balance': 200.0, 'amount_residual': 0.0, 'reconciled': True},
            {'balance': 800.0, 'amount_residual': 0.0, 'reconciled': True},
        ])


@tagged('post_install', '-at_install')
class TestAccountBatchPaymentAccountingOnly(TestAccountBatchPayment):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if cls.env['ir.module.module']._get('accountant').state != 'installed':
            cls.skipTest(cls, "This class tests payment without entries, which happens only when Accounting is installed")

    def test_change_payment_state_valid(self):
        """
        Check if the amount is well computed when we change a payment state into a non valid payment status
        """
        payments = self.env['account.payment']
        bank_journal_2 = self.company_data['default_journal_bank'].copy()
        for _ in range(2):
            payments += self.env['account.payment'].create({
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'supplier',
                'partner_id': self.partner_a.id,
                'journal_id': bank_journal_2.id,
            })
        payments.action_post()

        batch_payment = self.env['account.batch.payment'].create(
            {
                'journal_id': payments.journal_id.id,
                'payment_method_id': payments.payment_method_id.id,
                'payment_ids': [
                    (6, 0, payments.ids)
                ],
            }
        )

        self.assertRecordValues(batch_payment, [{
            'amount': 200.0,
            'amount_residual': 200.0,
            'amount_residual_currency': 200.0,
        }])

        # Change move state to 'reconciled', if accounting is installed it won't be a valid payment state for batches
        payments[0].action_validate()

        self.assertRecordValues(batch_payment, [{
            'amount': 200.0,
            'amount_residual': 100.0,
            'amount_residual_currency': 100.0,
        }])

    def test_partner_account_batch_payments_without_journal_entry(self):
        """ Test that account receivable is used for inbound payments and account payable for outbound ones
            when no journal entry is linked to the payment
        """
        for payment_type, account_a, account_b in [
            ('inbound', self.partner_a.property_account_receivable_id, self.partner_b.property_account_receivable_id),
            ('outbound', self.partner_a.property_account_payable_id, self.partner_b.property_account_payable_id),
        ]:
            payment_1 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 100.0,
            })
            payment_2 = self.env['account.payment'].create({
                'date': '2015-01-01',
                'payment_type': payment_type,
                'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
                'partner_id': self.partner_b.id,
                'payment_method_line_id': self.batch_deposit.id,
                'amount': 200.0,
            })
            payments = payment_1 + payment_2
            payments.action_post()
            batch = self.env['account.batch.payment'].create({
                'batch_type': payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payments.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
            batch.validate_batch()
            st_line_amount = 300.0 if payment_type == 'inbound' else -300.0
            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': self.journal.id,
                'amount': st_line_amount,
                'date': '2015-01-01',
                'payment_ref': batch.name,
            })
            st_line.set_batch_payment_bank_statement_line(batch.id)
            bank_account = self.journal.default_account_id
            if payment_type == 'inbound':
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': -200.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': 300.0},
                ])
            else:
                self.assertRecordValues(st_line.move_id.line_ids.sorted('balance'), [
                    {'account_id': bank_account.id, 'partner_id': False, 'balance': -300.0},
                    {'account_id': account_a.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
                    {'account_id': account_b.id, 'partner_id': self.partner_b.id, 'balance': 200.0},
                ])

    def test_bank_rec_widget_batch_payment_without_entries(self):
        payment = self.create_payment(self.partner_a, 100, payment_method_line_id=self.batch_deposit.id)
        payment.create_batch_payment()

        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'name': st_line.payment_ref, 'amount_currency': 100.0, 'currency_id': self.company_data['currency'].id, 'balance': 100.0, 'reconciled': False},
            {'account_id': self.partner_a.property_account_receivable_id.id, 'name': payment.name, 'amount_currency': -100.0, 'currency_id': self.company_data['currency'].id, 'balance': -100.0, 'reconciled': False},
        ])

    def test_bank_rec_widget_batch_with_epd_without_entries(self):
        st_line = self._create_st_line(180.0, date='2019-01-05')
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        invoice_lines_with_epd = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            price_unit=100.0,
        ) + self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            price_unit=100.0,
        )
        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice_lines_with_epd.move_id.ids,
        ).create({
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()

        batch = self.env['account.batch.payment'].create({
                'batch_type': payments[0].payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payments.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
        batch.validate_batch()

        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 180.0, 'balance': 180.0, 'reconciled': False},
            {'account_id': invoice_lines_with_epd[0].account_id.id, 'amount_currency': -100.0, 'balance': -100.0, 'reconciled': True},
            {'account_id': early_pay_acc.id, 'amount_currency': 10.0, 'balance': 10.0, 'reconciled': False},
            {'account_id': invoice_lines_with_epd[1].account_id.id, 'amount_currency': -100.0, 'balance': -100.0, 'reconciled': True},
            {'account_id': early_pay_acc.id, 'amount_currency': 10.0, 'balance': 10.0, 'reconciled': False},
        ])
        self.assertEqual(payments.mapped('state'), ['reconciled', 'reconciled'])
        self.assertEqual(batch.state, 'reconciled')

        st_line.delete_reconciled_line(st_line.line_ids[1].id)

        self.assertEqual(payments[0].state, 'paid')
        self.assertEqual(batch.state, 'sent')

    def test_bank_rec_widget_grouped_batch_with_epd_with_partial_without_entries(self):
        """ Tests a grouped payment without entry for invoices eligible for early payment discount
            and adding it as a batch payment in the bank rec widget.
            The first fully paid invoice should see its EPD applied while the second should be a partial.
        """
        st_line = self._create_st_line(200.0, date='2019-01-05')
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        invoice_lines_with_epd = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            price_unit=100.0,
        ) + self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            price_unit=100.0,
        )
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice_lines_with_epd.move_id.ids,
        ).create({
            'group_payment': True,
            'amount': 150,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()

        batch = self.env['account.batch.payment'].create({
                'batch_type': payment.payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payment.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
        batch.validate_batch()

        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 200.0, 'balance': 200.0, 'reconciled': False},
            {'account_id': invoice_lines_with_epd[0].account_id.id, 'amount_currency': -100.0, 'balance': -100.0, 'reconciled': True},
            {'account_id': early_pay_acc.id, 'amount_currency': 10.0, 'balance': 10.0, 'reconciled': False},
            {'account_id': invoice_lines_with_epd[1].account_id.id, 'amount_currency': -60.0, 'balance': -60.0, 'reconciled': True},
            {'account_id': st_line.journal_id.suspense_account_id.id, 'amount_currency': -50.0, 'balance': -50.0, 'reconciled': False},
        ])
        self.assertEqual(payment.state, 'reconciled')
        self.assertEqual(batch.state, 'reconciled')

        st_line.delete_reconciled_line(st_line.line_ids[1].id)

        self.assertEqual(payment.state, 'paid')
        self.assertEqual(batch.state, 'sent')

    def test_bank_rec_widget_batch_payment_without_entries_link_to_move(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 100,
                }),
            ],
        })
        invoice.action_post()
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids
        ).create({
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()

        payment.create_batch_payment()
        st_line = self._create_st_line(amount=100)
        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 100.0, 'balance': 100.0, 'reconciled': False},
            {'account_id': invoice.line_ids[-1].account_id.id, 'amount_currency': -100.0, 'balance': -100.0, 'reconciled': True},
        ])
        self.assertEqual(st_line.line_ids.reconciled_lines_ids, payment.invoice_ids.line_ids.filtered(lambda x: x.account_id.account_type == 'asset_receivable'))

        st_line.delete_reconciled_line(st_line.line_ids[-1].id)
        self.assertEqual(payment.state, 'paid')
        self.assertEqual(invoice.payment_state, 'in_payment')

    def test_bank_rec_widget_batch_move_link_to_multiple_payment_without_entries(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice.action_post()
        payment_1 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 400,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payment_2 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 600,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()

        (payment_1 + payment_2).create_batch_payment()
        st_line = self._create_st_line(amount=1000)
        st_line.set_batch_payment_bank_statement_line(payment_1.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 1000.0, 'balance': 1000.0, 'reconciled': False},
            {'account_id': invoice.line_ids[-1].account_id.id, 'amount_currency': -400.0, 'balance': -400.0, 'reconciled': True},
            {'account_id': invoice.line_ids[-1].account_id.id, 'amount_currency': -600.0, 'balance': -600.0, 'reconciled': True},
        ])
        st_line.delete_reconciled_line(st_line.line_ids[-1].id)
        self.assertEqual(payment_1.state, 'reconciled')
        self.assertEqual(payment_2.state, 'paid')
        self.assertEqual(invoice.payment_state, 'in_payment')

    def test_bank_rec_widget_batch_one_move_multiple_payment_without_entries(self):
        invoice_1 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_1.action_post()
        invoice_2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_2.action_post()

        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_1 + invoice_2).ids,
        ).create({
            'amount': 2000,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payments.create_batch_payment()
        st_line = self._create_st_line(amount=2000)
        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 2000.0, 'balance': 2000.0, 'reconciled': False},
            {'account_id': invoice_1.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
            {'account_id': invoice_2.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
        ])

    def test_bank_rec_widget_batch_one_move_multiple_payment_without_entries_grouped(self):
        invoice_1 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_1.action_post()
        invoice_2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        invoice_2.action_post()

        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_1 + invoice_2).ids,
        ).create({
            'amount': 2000,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
            'group_payment': True,
        })._create_payments()
        payments.create_batch_payment()
        st_line = self._create_st_line(amount=2000)
        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': 2000.0, 'balance': 2000.0, 'reconciled': False},
            {'account_id': invoice_1.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
            {'account_id': invoice_2.line_ids[-1].account_id.id, 'amount_currency': -1000.0, 'balance': -1000.0, 'reconciled': True},
        ])

    def test_bank_rec_widget_batch_without_entries_grouped_with_bills(self):
        bills_1 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        bills_1.action_post()
        bills_2 = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 1000,
                }),
            ],
        })
        bills_2.action_post()

        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(bills_1 + bills_2).ids,
        ).create({
            'amount': 2000,
            'payment_date': '2019-01-01',
            'payment_method_line_id': self.batch_deposit.id,
            'group_payment': True,
        })._create_payments()
        payments.create_batch_payment()
        st_line = self._create_st_line(amount=-2000)
        st_line.set_batch_payment_bank_statement_line(payments.batch_payment_id.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id, 'amount_currency': -2000.0, 'balance': -2000.0, 'reconciled': False},
            {'account_id': bills_1.line_ids[-1].account_id.id, 'amount_currency': 1000.0, 'balance': 1000.0, 'reconciled': True},
            {'account_id': bills_2.line_ids[-1].account_id.id, 'amount_currency': 1000.0, 'balance': 1000.0, 'reconciled': True},
        ])

    def test_bank_rec_widget_batch_with_epd_with_exch_diff_without_entries(self):
        """ Tests a batch payment of a grouped payment with an amount too large for:
                - 1 invoice with an early payment discount AND exchange diff
                - 1 invoice with an early payment discount
            During reconciliation, a payment with move should be created for the first invoice (to correctly handle the EPD),
            the second invoice should correctly be added to the widget, and the surplus should be added as a payment.
        """
        chf_currency = self.setup_other_currency('CHF', rates=[('2016-01-01', 2.0), ('2019-01-03', 4.0)])
        st_line = self._create_st_line(200.0, date='2019-01-05', foreign_currency_id=chf_currency.id)
        early_pay_acc = self.env.company.account_journal_early_pay_discount_loss_account_id
        invoice_with_exch_diff = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-01',
            invoice_payment_term_id=self.early_payment_term.id,
            price_unit=100.0,
            currency_id=chf_currency.id,
        )
        invoice_without_exch_diff = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-04',
            invoice_payment_term_id=self.early_payment_term.id,
            price_unit=100.0,
            currency_id=chf_currency.id,
        )
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_with_exch_diff + invoice_without_exch_diff).move_id.ids,
        ).create({
            'group_payment': True,
            'amount': 200,
            'payment_date': '2019-01-04',
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        outstanding_account = self.env['account.payment']._get_outstanding_account(payment.payment_type)

        batch = self.env['account.batch.payment'].create({
                'batch_type': payment.payment_type,
                'journal_id': self.journal.id,
                'payment_ids': [Command.set(payment.ids)],
                'payment_method_id': self.batch_deposit_method.id,
            })
        batch.validate_batch()
        self.assertEqual(batch.amount, 50.0)

        st_line.set_batch_payment_bank_statement_line(payment.batch_payment_id.id)
        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id,                'amount_currency': 200.0,   'balance': 200.0,   'reconciled': False},
            # The first invoice and payment have been changed into a payment with move to handle the exchange diff. The next line comes from that move.
            {'account_id': outstanding_account.id,                                  'amount_currency': -90.0,   'balance': -22.5,   'reconciled': True},
            # The 2 following lines correspond to the second invoice + EPD.
            {'account_id': invoice_without_exch_diff.account_id.id,                 'amount_currency': -100.0,  'balance': -25.0,   'reconciled': True},
            {'account_id': early_pay_acc.id,                                        'amount_currency': 10.0,    'balance': 2.5,     'reconciled': False},
            # The remaining amount from the payment is added as is.
            {'account_id': payment.partner_id.property_account_receivable_id.id,   'amount_currency': -20.0,   'balance': -5.0,    'reconciled': False},
            {'account_id': st_line.journal_id.suspense_account_id.id,               'amount_currency': -600.0,  'balance': -150.0,  'reconciled': False},
        ])
        self.assertEqual(payment.state, 'reconciled')
        self.assertEqual(batch.state, 'reconciled')
        self.assertEqual(payment.amount, 110.0, "The creation of the payment with move during reconciliation should have diminished the grouped payment amount.")

    def test_bank_rec_widget_batch_foreign_currency_journal_without_entries(self):
        """ Tests a batch payment of payments recorded in another journal with
            foreign currency and no outstanding account set.
            - 2 invoices in company currency paid in foreign currency
            - 1 bank transaction in foreign currency
        """
        chf_currency = self.setup_other_currency('CHF', rates=[('2019-01-01', 1.5)])
        foreign_journal = self.env['account.journal'].create({'name': 'CHF journal', 'type': 'bank', 'code': 'BNKX', 'currency_id': chf_currency.id})
        invoice_1 = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-01',
            price_unit=100.0,
        )
        invoice_2 = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            invoice_date='2019-01-01',
            price_unit=200.0,
        )
        payment_1 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice_1.move_id.ids,
        ).create({
            'amount': 150,
            'payment_date': '2019-01-01',
            'journal_id': foreign_journal.id,
        })._create_payments()

        payment_2 = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice_2.move_id.ids,
        ).create({
            'amount': 300,
            'payment_date': '2019-01-01',
            'journal_id': foreign_journal.id,
        })._create_payments()

        batch = self.env['account.batch.payment'].create({
                'batch_type': payment_1.payment_type,
                'journal_id': foreign_journal.id,
                'payment_ids': [Command.set((payment_1 | payment_2).ids)],
        })
        batch.validate_batch()
        st_line = self._create_st_line(450.0, date='2019-01-05', foreign_currency_id=chf_currency.id, journal_id=foreign_journal.id)
        st_line.set_batch_payment_bank_statement_line(batch.id)

        self.assertRecordValues(st_line.line_ids, [
            {'account_id': st_line.journal_id.default_account_id.id,    'amount_currency': 450.0,   'balance': 300.0,   'reconciled': False},
            {'account_id': invoice_1.account_id.id,                     'amount_currency': -150.0,  'balance': -100.0,   'reconciled': True},
            {'account_id': invoice_2.account_id.id,                     'amount_currency': -300.0,  'balance': -200.0,   'reconciled': True},
        ])
        self.assertEqual(invoice_1.move_id.payment_state, 'paid')
        self.assertEqual(invoice_2.move_id.payment_state, 'paid')
        self.assertEqual(batch.state, 'reconciled')

    def test_batch_payment_deletion(self):
        """ Make sure we can't delete a batch payment if we already sent it and generated an export file."""
        # This test needs account_iso20022 installed to be able to test with sepa_ct
        if self.env['ir.module.module']._get('account_iso20022').state != 'installed':
            self.skipTest("account_iso20022 not installed")

        self.partner_a.country_id = self.env.ref('base.be')
        eur_journal = self.env['account.journal'].create({
            'name': 'EUR Journals',
            'currency_id': self.env.ref('base.EUR').id,
            'code': 'Bnk EUR',
            'type': 'bank',
            'bank_account_number': 'BE48363523682327',
        })
        payment_method_line = eur_journal.outbound_payment_method_line_ids.filtered(lambda pml: pml.code == 'sepa_ct')[0]
        payments = self.env['account.payment'].create([{
            'date': '2025-01-01',
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_a.id,
            'journal_id': eur_journal.id,
            'payment_method_line_id': payment_method_line.id,
            'amount': 100.0,
        }, {
            'date': '2025-01-01',
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_a.id,
            'journal_id': eur_journal.id,
            'payment_method_line_id': payment_method_line.id,
            'amount': 200.0,
        }])
        payments.action_post()
        batch_payment_action = payments.create_batch_payment()
        batch_payment = self.env['account.batch.payment'].browse(batch_payment_action['res_id'])
        batch_payment.validate_batch_button()
        with self.assertRaisesRegex(UserError, "You can't delete a batch payment"):
            batch_payment.unlink()

    def test_payment_state_after_invoice_edition_without_journal_entry(self):
        """ Test that a bank statement reconciled with a batch payment is unreconciled and the state of all the payments
            is set to "In Process" when the amount of one of the invoices is modified.
        """
        self.partner_b.property_payment_term_id = self.pay_terms_a
        invoice_1 = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[90.0], post=True)
        invoice_2 = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[10.0], post=True)
        invoice_3 = self.init_invoice('out_invoice', partner=self.partner_b, amounts=[50.0], post=True)
        invoice_4 = self.init_invoice('out_invoice', partner=self.partner_b, amounts=[40.0], post=True)
        # create a group payment for invoice 1 and 2
        active_ids = (invoice_1 + invoice_2).ids
        group_payment = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=active_ids).create({
            'amount': 100.0,
            'group_payment': True,
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        # create a simple payment for invoice 3
        payment_3 = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice_3.ids).create({
            'amount': 50.0,
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        # create a simple payment for invoice 4
        payment_4 = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice_4.ids).create({
            'amount': 40.0,
            'payment_method_line_id': self.batch_deposit.id,
        })._create_payments()
        payments = group_payment + payment_3 + payment_4
        payments.action_post()
        # create a batch payment for the 3 payments
        batch_payment_action = payments.create_batch_payment()
        batch_payment = self.env['account.batch.payment'].browse(batch_payment_action.get('res_id'))
        batch_payment.validate_batch()
        # create a statement line and reconcile it with the batch payment
        st_line = self._create_st_line(190.0, payment_ref=batch_payment.name)
        st_line.set_batch_payment_bank_statement_line(batch_payment.id)

        self.assertTrue(st_line.is_reconciled)
        for payment in payments:
            self.assertEqual(payment.state, 'reconciled')
        # edit the price of invoice 3
        invoice_3.button_draft()
        with Form(invoice_3) as form:
            with form.invoice_line_ids.edit(0) as line_form:
                line_form.price_unit = 30.0

        self.assertFalse(st_line.is_reconciled)
        for payment in payments:
            self.assertEqual(payment.state, 'paid')
