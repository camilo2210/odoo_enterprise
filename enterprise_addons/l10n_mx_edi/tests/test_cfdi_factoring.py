from dateutil.relativedelta import relativedelta

from .common import TestMxEdiCommon

from odoo import fields, Command
from odoo.exceptions import ValidationError, UserError
from odoo.tests import tagged

from odoo.addons.account_accountant.tests.test_account_bank_statement_tour import TestAccountBankStatementTour


@tagged('post_install_l10n', 'post_install', '-at_install', *TestMxEdiCommon.extra_tags)
class TestCFDIFactoring(TestAccountBankStatementTour, TestMxEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def _create_factoring_payment(self, statement_line, move_lines, amount_vals_list=[], apply=True):
        factoring_wizard = self.env['l10n_mx_edi.register.factoring'].with_context({
            'statement_line_id': statement_line.id,
            'move_line_ids': move_lines.ids,
        }).create({})

        if amount_vals_list:
            for line, amount_vals in zip(factoring_wizard.line_ids, amount_vals_list):
                line.write(amount_vals)

        if apply:
            factoring_wizard.action_apply_factoring()

        return factoring_wizard

    def test_factoring_payment_simple(self):
        """Test factoring on a single invoice in MXN currency."""
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx()  # 1160 MXN
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': self.company_data['default_journal_bank'].id,
                'amount': 1000.00,  # MXN
                'payment_ref': 'PAY MXN Curr',
                'partner_id': self.partner_mx.id,
            })

            receivable_lines = invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
            amount_vals = [{'amount_trans_currency': 1000.00, 'compensation_amount_trans_currency': 160.00}]

            _factoring_wizard = self._create_factoring_payment(st_line, receivable_lines, amount_vals_list=amount_vals)

            _liquidity_lines, suspense_lines, other_lines = st_line._seek_for_lines()

            self.assertRecordValues(st_line, [{'is_reconciled': True}])
            self.assertTrue(not suspense_lines)
            self.assertRecordValues(invoice, [{'payment_state': 'paid'}])

            self.assertTrue(len(other_lines) == 3, 'Only a payment line, compensation line and factoring line cost should be created')

            # Each factoring payment at least creates three lines for invoice.
            #  - The line of the real payment amount that the factor institution issues
            #  - The line of compensation that usually covers or not the due amount of the invoice
            #  - The line of factoring costs
            self.assertRecordValues(other_lines, [
                {
                    'balance': -1000.00,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': False,
                }, {
                    'balance': -160.00,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': 'compensation'
                }, {
                    'balance': 160.00,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': False,
                    'l10n_mx_edi_factoring_type': 'factoring_cost',
                }
            ])

            with self.with_mocked_pac_sign_success():
                st_line.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(st_line.move_id, 'test_factoring_payment_simple')

    def test_factoring_payment_multi(self):
        """Test factoring with multiple invoices and on foreign currency."""
        usd_journal = self.env['account.journal'].create({
            'name': 'Bank USD',
            'code': 'BNKUSD',
            'type': 'bank',
            'company_id': self.env.company.id,
            'currency_id': self.env.ref('base.USD').id,
            'bank_account_number': '789101',
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_transferencia').id,
        })
        date1 = self.frozen_today - relativedelta(days=2)
        date2 = self.frozen_today - relativedelta(days=1)
        payment_date = self.frozen_today
        usd = self.setup_other_currency(
            code='USD',
            rates=[
                (fields.Date.subtract(date1, days=1), 0.053943),
                (fields.Date.subtract(date2, days=1), 0.053696),
                (fields.Date.subtract(payment_date, days=1), 0.054622422504)
            ],
        )

        with self.mx_external_setup(date1):
            invoice_1 = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        price_unit=16420.80,
                    ),
                ],
            )
            invoice_2 = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        price_unit=1129.92,
                    ),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice_1._l10n_mx_edi_cfdi_invoice_try_send()
                invoice_2._l10n_mx_edi_cfdi_invoice_try_send()

        with self.mx_external_setup(date2):
            invoice_3 = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        price_unit=1305.60
                    ),
                ],
            )
            invoice_4 = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 3916.80,
                    }),
                ],
            )

            with self.with_mocked_pac_sign_success():
                invoice_3._l10n_mx_edi_cfdi_invoice_try_send()
                invoice_4._l10n_mx_edi_cfdi_invoice_try_send()

        invoices = invoice_1 | invoice_2 | invoice_3 | invoice_4

        with self.mx_external_setup(payment_date):
            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': usd_journal.id,
                'amount': 25538.17,  # USD
                'payment_ref': 'PAY USD Curr',
                'partner_id': self.partner_mx.id,
            })

            receivable_lines = invoices.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')

            amounts_by_line = [
                {'amount_trans_currency': 18420.74, 'compensation_amount_trans_currency': 627.39},
                {'amount_trans_currency': 1267.55, 'compensation_amount_trans_currency': 43.16},
                {'amount_trans_currency': 1462.47, 'compensation_amount_trans_currency': 52.03},
                {'amount_trans_currency': 4387.41, 'compensation_amount_trans_currency': 156.08},
            ]

            _factoring_wizard = self._create_factoring_payment(st_line, receivable_lines, amount_vals_list=amounts_by_line)

            _liquidity_lines, suspense_lines, other_lines = st_line._seek_for_lines()

            self.assertRecordValues(st_line, [{'is_reconciled': True}])
            self.assertTrue(not suspense_lines)
            self.assertTrue(all(state == 'paid' for state in invoices.mapped('payment_state')), 'All invoices should be fully paid')
            normal_payment_lines = other_lines.filtered(lambda l: not l.l10n_mx_edi_factoring_type)
            # Assert normal payment lines
            self.assertRecordValues(normal_payment_lines.sorted('id'), [
                {
                    'amount_currency': -18420.74,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': False,
                }, {
                    'amount_currency': -1267.55,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': False,
                }, {
                    'amount_currency': -1462.47,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': False,
                }, {
                    'amount_currency': -4387.41,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': False,
                },
            ])

            # Assert compensation lines
            compensation_lines = other_lines.filtered(lambda l: l.l10n_mx_edi_factoring_type == 'compensation')
            self.assertRecordValues(compensation_lines, [
                {
                    'amount_currency': -627.39,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': 'compensation',
                }, {
                    'amount_currency': -43.16,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': 'compensation',
                }, {
                    'amount_currency': -52.03,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': 'compensation',
                }, {
                    'amount_currency': -156.08,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': True,
                    'l10n_mx_edi_factoring_type': 'compensation',
                },
            ])

            # Assert factoring lines
            factoring_lines = other_lines.filtered(lambda l: l.l10n_mx_edi_factoring_type == 'factoring_cost')
            factoring_account_id = self.env.company.l10n_mx_edi_factoring_account_id.id
            self.assertRecordValues(factoring_lines, [
                {
                    'amount_currency': 627.39,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': False,
                    'l10n_mx_edi_factoring_type': 'factoring_cost',
                    'account_id': factoring_account_id,
                }, {
                    'amount_currency': 43.16,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': False,
                    'l10n_mx_edi_factoring_type': 'factoring_cost',
                    'account_id': factoring_account_id,
                }, {
                    'amount_currency': 52.03,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': False,
                    'l10n_mx_edi_factoring_type': 'factoring_cost',
                    'account_id': factoring_account_id,

                }, {
                    'amount_currency': 156.08,
                    'currency_id': st_line.currency_id.id,
                    'reconciled': False,
                    'l10n_mx_edi_factoring_type': 'factoring_cost',
                    'account_id': factoring_account_id,
                }
            ])

            with self.with_mocked_pac_sign_success():
                st_line.move_id._l10n_mx_edi_cfdi_payment_try_send()

            self._assert_invoice_payment_cfdi(st_line.move_id, 'test_factoring_payment_multiple')

    def test_factoring_payment_with_payment_term(self):
        """Test the factoring when there is a payment term selected on the invoice."""
        mx_journal = self.env['account.journal'].create({
            'name': 'Bank MX',
            'code': 'BNKMX',
            'type': 'bank',
            'company_id': self.env.company.id,
            'currency_id': self.env.ref('base.MXN').id,
            'bank_account_number': '123456',
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_transferencia').id,
        })

        payment_term = self.env['account.payment.term'].create({
            'name': '30 today and then 70, 30 days later ',
            'line_ids': [
                Command.create({
                    'value_amount': 30,
                    'value': 'percent',
                    'nb_days': 0,
                }),
                Command.create({
                    'value_amount': 70,
                    'value': 'percent',
                    'nb_days': 30,
                }),
            ],
        })
        with self.mx_external_setup(self.frozen_today):
            invoice_with_term = self._create_invoice_mx(
                invoice_payment_term_id=payment_term,
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        price_unit=1000.0,
                        tax_ids=[]
                    ),
                ],
            )

            with self.with_mocked_pac_sign_success():
                invoice_with_term._l10n_mx_edi_cfdi_invoice_try_send()

            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': mx_journal.id,
                'amount': 900.00,  # MXN
                'payment_ref': 'PAY MXN Curr',
                'partner_id': self.partner_mx.id,
            })

            receivable_lines = invoice_with_term.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
            factoring_wizard = self._create_factoring_payment(st_line, receivable_lines, apply=False)

            self.assertRecordValues(factoring_wizard.line_ids, [
                # Two lines should have been created for each receivable
                {'amount_residual_currency': 300.0, 'amount_trans_currency': 0.0, 'compensation_amount_trans_currency': 0.0},
                {'amount_residual_currency': 700.0, 'amount_trans_currency': 0.0, 'compensation_amount_trans_currency': 0.0}
            ])

            amounts = [
                {'amount_trans_currency': 270.0, 'compensation_amount_trans_currency': 30.0},
                {'amount_trans_currency': 630.0, 'compensation_amount_trans_currency': 70.0},
            ]

            for line, amount_vals in zip(factoring_wizard.line_ids, amounts):
                line.write(amount_vals)

            factoring_wizard.action_apply_factoring()

            _liquidity_lines, suspense_lines, other_lines = st_line._seek_for_lines()

            self.assertRecordValues(st_line, [{'is_reconciled': True}])
            self.assertTrue(not suspense_lines)
            self.assertRecordValues(invoice_with_term, [{'payment_state': 'paid'}])

            # Assert that the combo of payment line / compensation line / factoring cost line was
            # created for each receivable line
            self.assertRecordValues(other_lines, [
                # First installment payment
                {'balance': -270.00, 'currency_id': st_line.currency_id.id, 'reconciled': True, 'l10n_mx_edi_factoring_type': False},
                {'balance': -30.00, 'currency_id': st_line.currency_id.id, 'reconciled': True, 'l10n_mx_edi_factoring_type': 'compensation'},
                {'balance': 30.00, 'currency_id': st_line.currency_id.id, 'reconciled': False, 'l10n_mx_edi_factoring_type': 'factoring_cost'},

                # Second installment payment
                {'balance': -630.00, 'currency_id': st_line.currency_id.id, 'reconciled': True, 'l10n_mx_edi_factoring_type': False},
                {'balance': -70.00, 'currency_id': st_line.currency_id.id, 'reconciled': True, 'l10n_mx_edi_factoring_type': 'compensation'},
                {'balance': 70.00, 'currency_id': st_line.currency_id.id, 'reconciled': False, 'l10n_mx_edi_factoring_type': 'factoring_cost'},
            ])

            with self.with_mocked_pac_sign_success():
                st_line.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(st_line.move_id, 'test_factoring_payment_with_payment_term')

    def test_factoring_payment_check(self):
        """Test that when trying to create and apply a factoring payment with an invalid state.
        the respective errors are raised.
        """
        other_mx_company_data = self.setup_other_company(name="Other MX Company", currency_id=self.env.ref('base.MXN').id)
        non_mx_company, non_mx_journal = self.non_mx_company_data['company'], self.non_mx_company_data['default_journal_bank']

        non_mx_st_line = self.env['account.bank.statement.line'].create({
            'journal_id': non_mx_journal.id,
            'amount': 100.00,  # MXN
            'payment_ref': 'PAY MXN Curr',
        })

        non_mx_invoice = self._create_invoice(
            partner_id=self.partner_a,
            company_id=non_mx_company,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.generic_product),
            ],
        )

        receivable_lines = non_mx_invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')

        # Assert that there should be a partner on the statement line
        with self.assertRaisesRegex(ValidationError, 'To register a factoring payment, you first need to set the factor contact in the payment.'):
            self._create_factoring_payment(non_mx_st_line, receivable_lines, apply=False)

        non_mx_st_line.partner_id = non_mx_company.partner_id

        # Assert that only mx statement lines can apply factoring
        with self.assertRaisesRegex(ValidationError, 'You cannot use factoring on this document'):
            self._create_factoring_payment(non_mx_st_line, receivable_lines, apply=False)

        mx_journal = self.company_data['default_journal_bank']
        mx_st_line = self.env['account.bank.statement.line'].create({
            'journal_id': mx_journal.id,
            'amount': 100.00,  # MXN
            'payment_ref': 'PAY MXN Curr',
            'partner_id': self.partner_mx.id,
        })

        # Assert that only mx documents can be used to apply factoring
        with self.assertRaisesRegex(ValidationError, 'Factoring is only allowed for posted customer invoices.'):
            self._create_factoring_payment(mx_st_line, receivable_lines, apply=False)

        mx_invoice = self._create_invoice_mx(post=False)
        mx_receivable_lines = mx_invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
        # Assert non posted invoices are not valid
        with self.assertRaisesRegex(ValidationError, 'Factoring is only allowed for posted customer invoices.'):
            self._create_factoring_payment(mx_st_line, mx_receivable_lines, apply=False)

        in_invoice = self._create_invoice_mx(move_type='in_invoice')
        # Assert only customer invoices
        with self.assertRaisesRegex(ValidationError, 'Factoring is only allowed for posted customer invoices.'):
            self._create_factoring_payment(mx_st_line, in_invoice.line_ids.filtered(lambda l: l.account_type == 'liability_payable'), apply=False)

        mx_invoice._post(soft=False)
        other_mx_invoice = self._create_invoice_mx(
            company_id=other_mx_company_data['company'],
            invoice_line_ids=[self._prepare_invoice_line(product_id=self.generic_product)]
        )
        other_receivable_lines = other_mx_invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
        # Assert that all lines should share the same company
        with self.assertRaisesRegex(ValidationError, 'All invoices must be from the same company.'):
            self._create_factoring_payment(mx_st_line, mx_receivable_lines | other_receivable_lines, apply=False)

        self._register_payment(mx_invoice)

        # Assert that there should be an amount to reconcile
        with self.assertRaisesRegex(ValidationError, "Some invoice lines don't have any remaing amount to be paid"):
            self._create_factoring_payment(mx_st_line, mx_receivable_lines, apply=False)

        valid_mx_invoice = self._create_invoice_mx()  # 1160 MXN
        factoring_wizard = self._create_factoring_payment(
            mx_st_line,
            valid_mx_invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable'),
            apply=False,
        )

        # All lines must have an amount
        with self.assertRaisesRegex(UserError, "You can't apply a factoring payment with a line with zero amount."):
            factoring_wizard.action_apply_factoring()

        # You can't pay more than what is due
        factoring_wizard.line_ids.amount_trans_currency = 2000.00
        with self.assertRaisesRegex(UserError, "You have paid more than what is due for some journal items."):
            factoring_wizard.action_apply_factoring()

        factoring_wizard.line_ids.amount_trans_currency = 1000.00
        self.env.company.l10n_mx_edi_factoring_account_id = False
        with self.assertRaisesRegex(UserError, "There is not a default factoring account set in your company."):
            factoring_wizard.action_apply_factoring()

    def test_factoring_payment_tour(self):
        """Test the factoring payment wizard flow."""
        self.env['account.bank.statement.line'].create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'amount': 900.00,  # MXN
            'payment_ref': 'Factoring Payment',
            'partner_id': self.partner_mx.id,
        })
        invoice = self._create_invoice_mx(
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product,
                    price_unit=1000.00,
                    tax_ids=[],
                ),
            ],
        )
        self.start_tour('/odoo', 'l10n_mx_edi_bank_rec_factoring', login=self.env.user.login)

        self.assertRecordValues(invoice, [{'payment_state': 'paid'}])
