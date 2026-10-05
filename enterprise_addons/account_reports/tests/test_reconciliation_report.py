# pylint: disable=C0326
from .common import TestAccountReportsCommon
from odoo import Command
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestReconciliationReport(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.other_currency = cls.setup_other_currency('EUR')
        cls.other_currency_2 = cls.setup_other_currency('GBP', rates=[('2015-12-31', 10.0), ('2016-12-31', 20.0)])

    def test_reconciliation_report_single_currency(self):
        """
            Tests the impact of positive/negative payments/statements on the reconciliation report in a single-currency
            environment.
        """
        bank_journal = self.env['account.journal'].create({
            'name': 'Bank',
            'code': 'BNKKK',
            'type': 'bank',
            'company_id': self.company_data['company'].id,
        })

        # ==== Payments ====
        self.inbound_payment_method_line.journal_id = bank_journal.id
        self.outbound_payment_method_line.journal_id = bank_journal.id
        payments = self.env['account.payment'].create([
            {
                'amount': 600.0,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'date': '2015-01-01',
                'journal_id': bank_journal.id,
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.inbound_payment_method_line.id,
            },
            {
                'amount': 500.0,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'date': '2015-01-01',
                'journal_id': bank_journal.id,
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.outbound_payment_method_line.id,
            },
            {
                'amount': 100.0,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'date': '2015-01-02',
                'journal_id': bank_journal.id,
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.inbound_payment_method_line.id,
            },
            {
                'amount': 200.0,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'date': '2015-01-03',
                'journal_id': bank_journal.id,
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.inbound_payment_method_line.id,
            },
            {
                'amount': 300.0,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'date': '2015-01-04',
                'journal_id': bank_journal.id,
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.outbound_payment_method_line.id,
            },
            {
                'amount': 400.0,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'date': '2015-01-05',
                'journal_id': bank_journal.id,
                'partner_id': self.partner_a.id,
                'payment_method_line_id': self.outbound_payment_method_line.id,
            },
        ])
        payments.action_post()

        # ==== Misc ====
        self.env['account.move'].create({
            'journal_id': bank_journal.id,
            'date': '2014-12-31',
            'line_ids': [
                (0, 0, {
                    'name': 'Source',
                    'debit': 1000,
                    'credit': 0,
                    'account_id': bank_journal.default_account_id.id,
                }),
                (0, 0, {
                    'name': 'Destination',
                    'debit': 0,
                    'credit': 1000,
                    'account_id': self.company_data['default_account_expense'].id,
                }),
            ]
        }).action_post()

        # ==== Statements ====
        self.env['account.bank.statement'].create({
            'name': 'statement_1',
            'date': '2015-01-01',
            'balance_start': 1000.0,
            'balance_end_real': 1100.0,
            'line_ids': [
                Command.create({'payment_ref': 'line_1', 'amount': 600.0, 'date': '2015-01-01', 'journal_id': bank_journal.id}),
                Command.create({'payment_ref': 'line_2', 'amount': -500.0, 'date': '2015-01-01', 'journal_id': bank_journal.id}),
            ],
        })

        statement_2 = self.env['account.bank.statement'].with_context(auto_statement_processing=True).create({
            'name': 'statement_2',
            'date': '2015-01-05',
            'balance_start': 1100.0,
            'balance_end_real': - 200.0,
            'journal_id': bank_journal.id,
            'line_ids': [
                Command.create({'payment_ref': 'line_1',    'amount': 100.0,    'date': '2015-01-02',    'partner_id': self.partner_a.id, 'journal_id': bank_journal.id}),
                Command.create({'payment_ref': 'line_2',    'amount': 200.0,    'date': '2015-01-03',                                     'journal_id': bank_journal.id}),
                Command.create({'payment_ref': 'line_3',    'amount': -300.0,   'date': '2015-01-04',    'partner_id': self.partner_a.id, 'journal_id': bank_journal.id}),
                Command.create({'payment_ref': 'line_4',    'amount': -400.0,   'date': '2015-01-05',                                     'journal_id': bank_journal.id}),
            ],
        })

        # ==== Reconciliation ====

        st_line = statement_2.line_ids.filtered(lambda line: line.payment_ref == 'line_2')
        payment_4 = payments[3]
        payment_line = payment_4.move_id.line_ids.filtered(lambda line: line.account_id == payment_4.payment_method_line_id.payment_account_id)
        st_line.set_line_bank_statement_line(payment_line.id)

        # ==== Report ====

        report = self.env.ref('account_reports.bank_reconciliation_report').with_context(
            active_id=bank_journal.id,
            active_model=bank_journal._name
        )
        account_name = bank_journal.default_account_id.display_name

        options = self._generate_options(report, '2015-01-01', '2015-01-31')
        options['unfold_all'] = True
        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                                       Date            Label        Amount
            [   0,                                                         1,              2,               3],
            [
                (account_name,                                             '',             '',             ''),
                ('Opening Bank Balance as of January 01 2015',             '',             '',         1000.0),
                ('Reconciled Transactions',                                '',             '',            0.0),
                ('Receipts',                                               '',             '',          300.0),
                ('BNKKK/2015/00004',                                       '01/03/2015',   'line_2',    200.0),
                ('BNKKK/2015/00003',                                       '01/02/2015',   'line_1',    100.0),
                ('Total Receipts',                                         '',             '',          300.0),
                ('Payments',                                               '',             '',         -300.0),
                ('BNKKK/2015/00005',                                       '01/04/2015',   'line_3',   -300.0),
                ('Total Payments',                                         '',             '',         -300.0),
                ('Total Reconciled Transactions',                          '',             '',            0.0),
                ('Unreconciled Transactions',                              '',             '',         -300.0),
                ('Receipts',                                               '',             '',          600.0),
                ('BNKKK/2015/00001',                                       '01/01/2015',   'line_1',    600.0),
                ('Total Receipts',                                         '',             '',          600.0),
                ('Payments',                                               '',             '',         -900.0),
                ('BNKKK/2015/00006',                                       '01/05/2015',   'line_4',   -400.0),
                ('BNKKK/2015/00002',                                       '01/01/2015',   'line_2',   -500.0),
                ('Total Payments',                                         '',             '',         -900.0),
                ('Total Unreconciled Transactions',                        '',             '',         -300.0),
                ('Misc. operations',                                       '',             '',            0.0),
                ('Calculated Ending Bank Balance as of January 31 2015',   '',             '',          700.0),
                ('Ending General Ledger Balance as of January 31 2015',    '',             '',          700.0),
                ('Outstanding Receipts/Payments',                          '',             '',         -300.0),
                ('(+) Outstanding Receipts',                               '',             '',          600.0),
                ('PBNKKK/2015/00001',                                      '01/01/2015',   '',          600.0),
                ('Total (+) Outstanding Receipts',                         '',             '',          600.0),
                ('(-) Outstanding Payments',                               '',             '',         -900.0),
                ('PBNKKK/2015/00006',                                      '01/05/2015',   '',         -400.0),
                ('PBNKKK/2015/00002',                                      '01/01/2015',   '',         -500.0),
                ('Total (-) Outstanding Payments',                         '',             '',         -900.0),
                ('Total Outstanding Receipts/Payments',                    '',             '',         -300.0),
            ],
            options,
        )

        options = self._generate_options(report, '2014-12-01', '2014-12-31')
        options['unfold_all'] = True
        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                                        Date            Label        Amount
            [   0,                                                          1,              2,               3],
            [
                (account_name,                                              '',             '',             ''),
                ('Opening Bank Balance as of December 01 2014',             '',             '',            0.0),
                ('Reconciled Transactions',                                 '',             '',            0.0),
                ('Receipts',                                                '',             '',            0.0),
                ('Payments',                                                '',             '',            0.0),
                ('Total Reconciled Transactions',                           '',             '',            0.0),
                ('Unreconciled Transactions',                               '',             '',            0.0),
                ('Receipts',                                                '',             '',            0.0),
                ('Payments',                                                '',             '',            0.0),
                ('Total Unreconciled Transactions',                         '',             '',            0.0),
                ('Misc. operations',                                        '',             '',         1000.0),
                ('BNKKK/2014/00001',                                        '12/31/2014',   '',         1000.0),
                ('Total Misc. operations',                                  '',             '',         1000.0),
                ('Calculated Ending Bank Balance as of December 31 2014',   '',             '',         1000.0),
                ('Ending General Ledger Balance as of December 31 2014',    '',             '',         1000.0),
                ('Outstanding Receipts/Payments',                           '',             '',            0.0),
                ('(+) Outstanding Receipts',                                '',             '',            0.0),
                ('(-) Outstanding Payments',                                '',             '',            0.0),
                ('Total Outstanding Receipts/Payments',                     '',             '',            0.0),
            ],
            options,
        )

    def test_reconciliation_report_multi_currencies(self):
        """ Tests the management of multi-currencies in the reconciliation report. """
        self.env.user.group_ids |= self.env.ref('base.group_multi_currency')
        self.env.user.group_ids |= self.env.ref('base.group_no_one')

        company_currency = self.company_data['currency']  # USD
        journal_currency = self.other_currency  # EUR
        choco_currency = self.other_currency_2  # GBP

        # ==== Journal with a foreign currency ====

        bank_journal = self.env['account.journal'].create({
            'name': 'Bank',
            'code': 'BNKKK',
            'type': 'bank',
            'company_id': self.company_data['company'].id,
            'currency_id': journal_currency.id
        })

        # ==== Statement ====

        bank_statement = self.env['account.bank.statement'].create({
            'name': 'statement',
            'line_ids': [

                # Transaction in the company currency.
                (0, 0, {
                    'payment_ref': 'line_1',
                    'date': '2016-01-01',
                    'amount': 100.0,
                    'journal_id': bank_journal.id,
                    'amount_currency': 50.01,
                    'foreign_currency_id': company_currency.id,
                }),

                # Transaction in a third currency.
                (0, 0, {
                    'payment_ref': 'line_3',
                    'date': '2016-01-01',
                    'amount': 100.0,
                    'journal_id': bank_journal.id,
                    'amount_currency': 999.99,
                    'foreign_currency_id': choco_currency.id,
                }),

            ],
        })

        # Partially reconcile the suspense amount associated with each bank statement line
        suspense_account = bank_journal.suspense_account_id
        other_account = bank_journal.company_id.default_cash_difference_income_account_id

        # the first is in company currency
        bank_move_1 = bank_statement.line_ids[0].move_id
        bank_move_1_suspense_line = bank_move_1.line_ids.filtered(lambda l: l.account_id == suspense_account)
        bank_move_1.button_draft()
        bank_move_1.write({'line_ids': [
            Command.create({'account_id': other_account.id, 'credit': 10.00}),
            Command.update(bank_move_1_suspense_line.id, {'credit': 40.01}),
        ]})
        bank_move_1.action_post()

        # the second is in neither company nor journal currency
        bank_move_2 = bank_statement.line_ids[1].move_id
        bank_move_2_suspense_line = bank_move_2.line_ids.filtered(lambda l: l.account_id == suspense_account)
        bank_move_2.button_draft()
        bank_move_2.write({'line_ids': [
            Command.create({
                'account_id': other_account.id,
                'currency_id': bank_move_2_suspense_line.currency_id.id,
                'credit': 3.33,
                'amount_currency': -99.99
            }),
            Command.update(bank_move_2_suspense_line.id, {
                'credit': 30.0,
                'amount_currency': -900.0
            }),
        ]})
        bank_move_2.action_post()

        # ==== Payments ====
        self.inbound_payment_method_line.journal_id = bank_journal.id
        # Payment in the company's currency.
        payment_1 = self.env['account.payment'].create({
            'amount': 1000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'date': '2016-01-01',
            'journal_id': bank_journal.id,
            'partner_id': self.partner_a.id,
            'currency_id': company_currency.id,
            'payment_method_line_id': self.inbound_payment_method_line.id,
        })

        # Payment in the same foreign currency as the journal.
        payment_2 = self.env['account.payment'].create({
            'amount': 2000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'date': '2016-01-01',
            'journal_id': bank_journal.id,
            'partner_id': self.partner_a.id,
            'currency_id': journal_currency.id,
            'payment_method_line_id': self.inbound_payment_method_line.id,
        })

        # Payment in a third foreign currency.
        payment_3 = self.env['account.payment'].create({
            'amount': 3000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'date': '2016-01-01',
            'journal_id': bank_journal.id,
            'partner_id': self.partner_a.id,
            'currency_id': choco_currency.id,
            'payment_method_line_id': self.inbound_payment_method_line.id,
        })
        (payment_1 + payment_2 + payment_3).action_post()

        # ==== Misc Entry ====

        move = self.env['account.move'].create({
            'journal_id': self.company_data['default_journal_misc'].id,
            'date': '2016-01-01',
            'line_ids': [
                Command.create({
                    'name': 'Line1',
                    'debit': 100,
                    'credit': 0,
                    'amount_currency': 200,
                    'account_id': bank_journal.default_account_id.id,
                    'currency_id': journal_currency.id
                }),
                Command.create({
                    'name': 'Line2',
                    'debit': 0,
                    'credit': 100,
                    'account_id': other_account.id,
                }),
            ]
        })
        move.action_post()

        # ==== Report ====

        report = self.env.ref('account_reports.bank_reconciliation_report').with_context(
            active_id=bank_journal.id,
            active_model=bank_journal._name
        )
        account_name = bank_journal.default_account_id.display_name

        with self.debug_mode():
            options = self._generate_options(report, '2016-01-01', '2016-01-31')
            options['unfold_all'] = True
            lines = report._get_lines(options)

            self.assertLinesValues(
                lines,
                #   Name                                                       Date            Label       Amount Currency     Amount
                [   0,                                                         1,              2,          3,                      4],
                [
                    (account_name,                                             '',             '',         '',                    ''),
                    ('Opening Bank Balance as of January 01 2016',             '',             '',         '',                   0.0),
                    ('Reconciled Transactions',                                '',             '',         '',                  30.0),
                    ('Receipts',                                               '',             '',         '',                  30.0),
                    ('BNKKK/2016/00002',                                       '01/01/2016',   'line_3',   '£\xa099.99',        10.0),
                    ('BNKKK/2016/00001',                                       '01/01/2016',   'line_1',   '$\xa010.00',        20.0),
                    ('Total Receipts',                                         '',             '',         '',                  30.0),
                    ('Payments',                                               '',             '',         '',                   0.0),
                    ('Total Reconciled Transactions',                          '',             '',         '',                  30.0),
                    ('Unreconciled Transactions',                              '',             '',         '',                 170.0),
                    ('Receipts',                                               '',             '',         '',                 170.0),
                    ('BNKKK/2016/00002',                                       '01/01/2016',   'line_3',   '£\xa0900.00',       90.0),
                    ('BNKKK/2016/00001',                                       '01/01/2016',   'line_1',   '$\xa040.01',        80.0),
                    ('Total Receipts',                                         '',             '',         '',                 170.0),
                    ('Payments',                                               '',             '',         '',                   0.0),
                    ('Total Unreconciled Transactions',                        '',             '',         '',                 170.0),
                    ('Misc. operations',                                       '',             '',         '',                 200.0),
                    ('MISC/2016/01/0001',                                      '01/01/2016',   '',         '',                 200.0),
                    ('Total Misc. operations',                                 '',             '',         '',                 200.0),
                    ('Calculated Ending Bank Balance as of January 31 2016',   '',             '',         '',                 400.0),
                    ('Ending General Ledger Balance as of January 31 2016',    '',             '',         '',                 400.0),
                    ('Outstanding Receipts/Payments',                          '',             '',         '',                5900.0),
                    ('(+) Outstanding Receipts',                               '',             '',         '',                5900.0),
                    ('PBNKKK/2016/00003',                                      '01/01/2016',   '',         '£\xa03,000.00',    900.0),
                    ('PBNKKK/2016/00002',                                      '01/01/2016',   '',         '',                2000.0),
                    ('PBNKKK/2016/00001',                                      '01/01/2016',   '',         '$\xa01,000.00',   3000.0),
                    ('Total (+) Outstanding Receipts',                         '',             '',         '',                5900.0),
                    ('(-) Outstanding Payments',                               '',             '',         '',                   0.0),
                    ('Total Outstanding Receipts/Payments',                    '',             '',         '',                5900.0),
                ],
                options,
                currency_map={4: {'currency': journal_currency}},
            )

    def test_reconciliation_change_date(self):
        """
            Tests that openeing/ending balance and transactions are correct with change in report date options..
        """
        bank_journal = self.company_data['default_journal_bank']

        statement = self.env['account.bank.statement'].create({
            'name': 'statement_1',
            'date': '2019-01-10',
            'balance_start': 1000.0,
            'balance_end_real': 1130.0,
            'line_ids': [
                (0, 0, {'payment_ref': 'line_1', 'amount': 10.0, 'date': '2019-01-01', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_2', 'amount': 20.0, 'date': '2019-01-02', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_3', 'amount': 30.0, 'date': '2019-01-03', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_4', 'amount': -40.0, 'date': '2019-01-04', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_5', 'amount': 50.0, 'date': '2019-01-05', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_6', 'amount': 60.0, 'date': '2019-01-06', 'journal_id': bank_journal.id}),
            ],
        })

        # This will allow to test if the balance of the bank account is changed
        statement['balance_end_real'] = 1140.0

        payment = self.env['account.payment'].create({
            'amount': 1000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'date': '2019-01-03',
            'journal_id': bank_journal.id,
            'partner_id': self.partner_a.id,
        })
        payment.action_post()

        report = self.env.ref('account_reports.bank_reconciliation_report').with_context(
            active_id=bank_journal.id,
            active_model='account.journal'
        )
        account_name = bank_journal.default_account_id.display_name

        options = self._generate_options(report, '2019-01-01', '2019-01-02')
        options['unfold_all'] = True
        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                                         Date            Label        Amount
            [   0,                                                           1,              2,               3],
            [
                (account_name,                                               '',             '',             ''),
                ('Opening Bank Balance as of January 01 2019',               '',             '',         1000.0),
                ('Reconciled Transactions',                                  '',             '',            0.0),
                ('Receipts',                                                 '',             '',            0.0),
                ('Payments',                                                 '',             '',            0.0),
                ('Total Reconciled Transactions',                            '',             '',            0.0),
                ('Unreconciled Transactions',                                '',             '',           30.0),
                ('Receipts',                                                 '',             '',           30.0),
                ('BNK1/2019/00002',                                          '01/02/2019',   'line_2',     20.0),
                ('BNK1/2019/00001',                                          '01/01/2019',   'line_1',     10.0),
                ('Total Receipts',                                           '',             '',           30.0),
                ('Payments',                                                 '',             '',            0.0),
                ('Total Unreconciled Transactions',                          '',             '',           30.0),
                ('Misc. operations',                                         '',             '',            0.0),
                ('Calculated Ending Bank Balance as of January 02 2019',     '',             '',         1030.0),
                ('Ending General Ledger Balance as of January 02 2019',      '',             '',           30.0),
                ('Outstanding Receipts/Payments',                            '',             '',            0.0),
                ('(+) Outstanding Receipts',                                 '',             '',            0.0),
                ('(-) Outstanding Payments',                                 '',             '',            0.0),
                ('Total Outstanding Receipts/Payments',                      '',             '',            0.0),
            ],
            options,
        )

        options = self._generate_options(report, '2019-01-01', '2019-01-31')
        options['unfold_all'] = True
        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                                             Date             Label       Amount
            [   0,                                                               1,               2,              3],
            [
                (account_name,                                                   '',             '',             ''),
                ('Opening Bank Balance as of January 01 2019',                   '',             '',         1000.0),
                ('Reconciled Transactions',                                      '',             '',            0.0),
                ('Receipts',                                                     '',             '',            0.0),
                ('Payments',                                                     '',             '',            0.0),
                ('Total Reconciled Transactions',                                '',             '',            0.0),
                ('Unreconciled Transactions',                                    '',             '',          130.0),
                ('Receipts',                                                     '',             '',          170.0),
                ('BNK1/2019/00006',                                              '01/06/2019',   'line_6',     60.0),
                ('BNK1/2019/00005',                                              '01/05/2019',   'line_5',     50.0),
                ('BNK1/2019/00003',                                              '01/03/2019',   'line_3',     30.0),
                ('BNK1/2019/00002',                                              '01/02/2019',   'line_2',     20.0),
                ('BNK1/2019/00001',                                              '01/01/2019',   'line_1',     10.0),
                ('Total Receipts',                                               '',             '',          170.0),
                ('Payments',                                                     '',             '',          -40.0),
                ('BNK1/2019/00004',                                              '01/04/2019',   'line_4',    -40.0),
                ('Total Payments',                                               '',             '',          -40.0),
                ('Total Unreconciled Transactions',                              '',             '',          130.0),
                ('Misc. operations',                                             '',             '',            0.0),
                ('Calculated Ending Bank Balance as of January 31 2019',         '',             '',         1130.0),
                ('Ending General Ledger Balance as of January 31 2019',          '',             '',          130.0),
                ('Outstanding Receipts/Payments',                                '',             '',         1000.0),
                ('(+) Outstanding Receipts',                                     '',             '',         1000.0),
                ('PBNK1/2019/00001',                                             '01/03/2019',   '',         1000.0),
                ('Total (+) Outstanding Receipts',                               '',             '',         1000.0),
                ('(-) Outstanding Payments',                                     '',             '',            0.0),
                ('Total Outstanding Receipts/Payments',                          '',             '',         1000.0),
            ],
            options,
        )

    def test_reconciliation_report_non_statement_payment(self):
        """
            Test that moves not linked to a bank statement/payment but linked for example to expenses are all showing in the
            report
        """
        bank_journal = self.env['account.journal'].create({
            'name': 'Bank',
            'code': 'BNKKK',
            'type': 'bank',
            'company_id': self.company_data['company'].id,
        })
        bank_journal.inbound_payment_method_line_ids.payment_account_id = self.inbound_payment_method_line.payment_account_id

        # ==== Misc ====
        self.env['account.move'].create({
            'journal_id': bank_journal.id,
            'date': '2014-12-31',
            'line_ids': [
                (0, 0, {
                    'name': 'Source',
                    'debit': 800,
                    'credit': 0,
                    'account_id': self.company_data['default_account_expense'].id,
                }),
                (0, 0, {
                    'name': 'Destination',
                    'debit': 0,
                    'credit': 800,
                    'account_id': self.inbound_payment_method_line.payment_account_id.id,
                }),
            ]
        }).action_post()

        self.env['account.move'].create({
            'journal_id': bank_journal.id,
            'date': '2015-12-31',
            'line_ids': [
                (0, 0, {
                    'name': 'Source',
                    'debit': 500,
                    'credit': 0,
                    'account_id': self.company_data['default_account_expense'].id,
                }),
                (0, 0, {
                    'name': 'Destination',
                    'debit': 0,
                    'credit': 500,
                    'account_id': self.inbound_payment_method_line.payment_account_id.id,
                }),
            ]
        }).action_post()

        # ==== Report ====

        report = self.env.ref('account_reports.bank_reconciliation_report').with_context(
            active_id=bank_journal.id,
            active_model='account.journal'
        )
        account_name = bank_journal.default_account_id.display_name

        options = self._generate_options(report, '2016-01-02', '2016-01-02')
        options['unfold_all'] = True
        lines = report._get_lines(options)

        self.assertLinesValues(
            lines,
            #   Name                                                         Date            Label         Amount
            [   0,                                                           1,              2,                3],
            [
                (account_name,                                               '',             '',              ''),
                ('Opening Bank Balance as of January 02 2016',               '',             '',             0.0),
                ('Reconciled Transactions',                                  '',             '',             0.0),
                ('Receipts',                                                 '',             '',             0.0),
                ('Payments',                                                 '',             '',             0.0),
                ('Total Reconciled Transactions',                            '',             '',             0.0),
                ('Unreconciled Transactions',                                '',             '',             0.0),
                ('Receipts',                                                 '',             '',             0.0),
                ('Payments',                                                 '',             '',             0.0),
                ('Total Unreconciled Transactions',                          '',             '',             0.0),
                ('Misc. operations',                                         '',             '',             0.0),
                ('Calculated Ending Bank Balance as of January 02 2016',     '',             '',             0.0),
                ('Ending General Ledger Balance as of January 02 2016',      '',             '',             0.0),
                ('Outstanding Receipts/Payments',                            '',             '',         -1300.0),
                ('(+) Outstanding Receipts',                                 '',             '',             0.0),
                ('(-) Outstanding Payments',                                 '',             '',         -1300.0),
                ('BNKKK/2015/00001',                                         '12/31/2015',   '',          -500.0),
                ('BNKKK/2014/00001',                                         '12/31/2014',   '',          -800.0),
                ('Total (-) Outstanding Payments',                           '',             '',         -1300.0),
                ('Total Outstanding Receipts/Payments',                      '',             '',         -1300.0),
            ],
            options,
        )

    def test_reconciliation_report_delete_statement(self):
        """ This test will do a basic flow where we create a statement and then we delete it to see how the report react"""

        bank_journal = self.company_data['default_journal_bank']

        statement = self.env['account.bank.statement'].create({
            'name': 'statement_1',
            'date': '2019-01-10',
            'balance_start': 1000.0,
            'balance_end_real': 1130.0,
            'line_ids': [
                (0, 0, {'payment_ref': 'line_1', 'amount': 10.0, 'date': '2018-12-31', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_2', 'amount': 20.0, 'date': '2019-01-02', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_3', 'amount': 30.0, 'date': '2019-01-03', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_4', 'amount': -40.0, 'date': '2019-01-04', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_5', 'amount': 50.0, 'date': '2019-01-05', 'journal_id': bank_journal.id}),
                (0, 0, {'payment_ref': 'line_6', 'amount': 60.0, 'date': '2019-01-06', 'journal_id': bank_journal.id}),
            ],
        })

        report = self.env.ref('account_reports.bank_reconciliation_report').with_context(
            active_id=bank_journal.id,
            active_model='account.journal'
        )
        account_name = bank_journal.default_account_id.display_name
        options = self._generate_options(report, '2019-01-01', '2019-01-12')
        options['unfold_all'] = True

        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                                             Date            Label        Amount
            [   0,                                                               1,              2,               3],
            [
                (account_name,                                                   '',             '',             ''),
                ('Opening Bank Balance as of January 01 2019',                   '',             '',         1010.0),
                ('Reconciled Transactions',                                      '',             '',            0.0),
                ('Receipts',                                                     '',             '',            0.0),
                ('Payments',                                                     '',             '',            0.0),
                ('Total Reconciled Transactions',                                '',             '',            0.0),
                ('Unreconciled Transactions',                                    '',             '',          120.0),
                ('Receipts',                                                     '',             '',          160.0),
                ('BNK1/2019/00005',                                              '01/06/2019',   'line_6',     60.0),
                ('BNK1/2019/00004',                                              '01/05/2019',   'line_5',     50.0),
                ('BNK1/2019/00002',                                              '01/03/2019',   'line_3',     30.0),
                ('BNK1/2019/00001',                                              '01/02/2019',   'line_2',     20.0),
                ('Total Receipts',                                               '',             '',          160.0),
                ('Payments',                                                     '',             '',          -40.0),
                ('BNK1/2019/00003',                                              '01/04/2019',   'line_4',    -40.0),
                ('Total Payments',                                               '',             '',          -40.0),
                ('Total Unreconciled Transactions',                              '',             '',          120.0),
                ('Misc. operations',                                             '',             '',            0.0),
                ('Calculated Ending Bank Balance as of January 12 2019',         '',             '',         1130.0),
                ('Ending General Ledger Balance as of January 12 2019',          '',             '',          130.0),
                ('Outstanding Receipts/Payments',                                '',             '',            0.0),
                ('(+) Outstanding Receipts',                                     '',             '',            0.0),
                ('(-) Outstanding Payments',                                     '',             '',            0.0),
                ('Total Outstanding Receipts/Payments',                          '',             '',            0.0),
            ],
            options,
        )

        statement.unlink()

        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                                              Date            Label       Amount
            [   0,                                                                1,              2,              3],
            [
                (account_name,                                                   '',             '',             ''),
                ('Opening Bank Balance as of January 01 2019',                   '',             '',           10.0),
                ('Reconciled Transactions',                                      '',             '',            0.0),
                ('Receipts',                                                     '',             '',            0.0),
                ('Payments',                                                     '',             '',            0.0),
                ('Total Reconciled Transactions',                                '',             '',            0.0),
                ('Unreconciled Transactions',                                    '',             '',          120.0),
                ('Receipts',                                                     '',             '',          160.0),
                ('BNK1/2019/00005',                                              '01/06/2019',   'line_6',     60.0),
                ('BNK1/2019/00004',                                              '01/05/2019',   'line_5',     50.0),
                ('BNK1/2019/00002',                                              '01/03/2019',   'line_3',     30.0),
                ('BNK1/2019/00001',                                              '01/02/2019',   'line_2',     20.0),
                ('Total Receipts',                                               '',             '',          160.0),
                ('Payments',                                                     '',             '',          -40.0),
                ('BNK1/2019/00003',                                              '01/04/2019',   'line_4',    -40.0),
                ('Total Payments',                                               '',             '',          -40.0),
                ('Total Unreconciled Transactions',                              '',             '',          120.0),
                ('Misc. operations',                                             '',             '',            0.0),
                ('Calculated Ending Bank Balance as of January 12 2019',         '',             '',          130.0),
                ('Ending General Ledger Balance as of January 12 2019',          '',             '',          130.0),
                ('Outstanding Receipts/Payments',                                '',             '',            0.0),
                ('(+) Outstanding Receipts',                                     '',             '',            0.0),
                ('(-) Outstanding Payments',                                     '',             '',            0.0),
                ('Total Outstanding Receipts/Payments',                          '',             '',            0.0),
            ],
            options,
        )

    def test_reconciliation_report_exchange_entry(self):
        """ This test will check that misc entries reported in the exchange journal
            do not figure in the report
        """

        bank_journal = self.company_data['default_journal_bank']
        exchange_journal = self.env.company.currency_exchange_journal_id

        move_a = self.env['account.move'].create({
                'journal_id': exchange_journal.id,
                'move_type': 'entry',
                'date': '2019-01-01',
                'line_ids': [
                    Command.create({
                        'name': 'line_a_1',
                        'account_id': bank_journal.default_account_id.id,
                        'debit': 1000.0,
                        'credit': 0.0,
                    }),
                    Command.create({
                        'name': 'line_a_2',
                        'account_id': self.company_data['default_account_expense'].id,
                        'debit': 0.0,
                        'credit': 1000.0,
                    }),
                ]
        })
        move_a.action_post()

        report = self.env.ref('account_reports.bank_reconciliation_report').with_context(
            active_id=bank_journal.id,
            active_model='account.journal'
        )
        account_name = bank_journal.default_account_id.display_name
        options = self._generate_options(report, '2019-01-01', '2019-01-12')
        lines = report._get_lines(options)

        self.assertLinesValues(
            lines,
            #   Name                                                             Date            Label        Amount
            [   0,                                                               1,              2,               3],
            [
                (account_name,                                                   '',             '',             ''),
                ('Opening Bank Balance as of January 01 2019',                   '',             '',            0.0),
                ('Reconciled Transactions',                                      '',             '',            0.0),
                ('Receipts',                                                     '',             '',            0.0),
                ('Payments',                                                     '',             '',            0.0),
                ('Total Reconciled Transactions',                                '',             '',            0.0),
                ('Unreconciled Transactions',                                    '',             '',            0.0),
                ('Receipts',                                                     '',             '',            0.0),
                ('Payments',                                                     '',             '',            0.0),
                ('Total Unreconciled Transactions',                              '',             '',            0.0),
                ('Misc. operations',                                             '',             '',            0.0),
                ('Calculated Ending Bank Balance as of January 12 2019',         '',             '',            0.0),
                ('Ending General Ledger Balance as of January 12 2019',          '',             '',         1000.0),
                ('Outstanding Receipts/Payments',                                '',             '',            0.0),
                ('(+) Outstanding Receipts',                                     '',             '',            0.0),
                ('(-) Outstanding Payments',                                     '',             '',            0.0),
                ('Total Outstanding Receipts/Payments',                          '',             '',            0.0),
            ],
            options,
        )
