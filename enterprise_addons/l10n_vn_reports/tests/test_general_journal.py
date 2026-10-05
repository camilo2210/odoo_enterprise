# ruff: noqa: E241, E201
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nVnGeneralJournal(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('vn')
    def setUpClass(cls):
        super().setUpClass()

        cls.general_journal_report = cls.env.ref('l10n_vn_reports.general_journal_report_l10n_vn')

        cls.receivable = cls.company_data['default_account_receivable']
        cls.revenue = cls.company_data['default_account_revenue']
        cls.expense = cls.company_data['default_account_expense']
        cls.payable = cls.company_data['default_account_payable']
        cls.assets = cls.company_data['default_account_assets']
        cls.misc_journal = cls.company_data['default_journal_misc']

        cls.receivable_disp = f"{cls.receivable.code} {cls.receivable.name}"
        cls.revenue_disp = f"{cls.revenue.code} {cls.revenue.name}"
        cls.expense_disp = f"{cls.expense.code} {cls.expense.name}"
        cls.payable_disp = f"{cls.payable.code} {cls.payable.name}"
        cls.assets_disp = f"{cls.assets.code} {cls.assets.name}"

    @freeze_time('2026-04-01')
    def test_general_journal_report(self):
        """Entries are listed chronologically, each one unfolding into its own move lines with their counterpart."""
        self.env['account.move'].create([
            # Move 1: 1-to-1  (one debit line ↔ one credit line)
            {
                'move_type': 'entry',
                'journal_id': self.misc_journal.id,
                'date': '2026-01-10',
                'line_ids': [
                    Command.create({'account_id': self.receivable.id, 'debit': 1000.0, 'credit': 0.0, 'name': 'Customer receivable'}),
                    Command.create({'account_id': self.revenue.id, 'debit': 0.0, 'credit': 1000.0, 'name': 'Revenue'}),
                ],
            },
            # Move 2: 1-to-N  (one debit line ↔ two credit lines)
            {
                'move_type': 'entry',
                'journal_id': self.misc_journal.id,
                'date': '2026-02-10',
                'line_ids': [
                    Command.create({'account_id': self.assets.id, 'debit': 1100.0, 'credit': 0.0, 'name': 'Asset receipt'}),
                    Command.create({'account_id': self.revenue.id, 'debit': 0.0, 'credit': 1000.0, 'name': 'Revenue'}),
                    Command.create({'account_id': self.expense.id, 'debit': 0.0, 'credit': 100.0, 'name': 'Expense credit'}),
                ],
            },
            # Move 3: N-to-1  (two debit lines ↔ one credit line)
            {
                'move_type': 'entry',
                'journal_id': self.misc_journal.id,
                'date': '2026-03-10',
                'line_ids': [
                    Command.create({'account_id': self.expense.id, 'debit': 600.0, 'credit': 0.0, 'name': 'Operating expense'}),
                    Command.create({'account_id': self.assets.id, 'debit': 60.0, 'credit': 0.0, 'name': 'Prepaid expense'}),
                    Command.create({'account_id': self.payable.id, 'debit': 0.0, 'credit': 660.0, 'name': 'Supplier payable'}),
                ],
            },
        ]).action_post()

        options = self._generate_options(self.general_journal_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev, exp, pay, ast = (
            self.receivable_disp, self.revenue_disp,
            self.expense_disp, self.payable_disp, self.assets_disp,
        )

        self.assertLinesValues(
            self.general_journal_report._get_lines(options),
            #   Name                                      Date           Partner  Counterpart  Currency    Debit    Credit
            [   0,                                        1,             2,       3,           4,          5,       6],
            [
                ('General Journal',                       '',            '',      '',          '',        2760.0,  2760.0),

                # 1-to-1
                ('MISC/2026/01/0001',                     '01/10/2026',  '',      '',          '',        1000.0,  1000.0),
                    (f'{rcv} Customer receivable',        '01/10/2026',  '',      rev,         '',        1000.0,     0.0),
                    (f'{rev} Revenue',                    '01/10/2026',  '',      rcv,         '',           0.0,  1000.0),
                ('Total MISC/2026/01/0001',               '01/10/2026',  '',      '',          '',        1000.0,  1000.0),

                # 1-to-N: the sole debit is split proportionally over both credits
                ('MISC/2026/02/0001',                     '02/10/2026',  '',      '',          '',        1100.0,  1100.0),
                    (f'{ast} Asset receipt',              '02/10/2026',  '',      rev,         '',        1000.0,     0.0),
                    (f'{ast} Asset receipt',              '02/10/2026',  '',      exp,         '',         100.0,     0.0),
                    (f'{rev} Revenue',                    '02/10/2026',  '',      ast,         '',           0.0,  1000.0),
                    (f'{exp} Expense credit',             '02/10/2026',  '',      ast,         '',           0.0,   100.0),
                ('Total MISC/2026/02/0001',               '02/10/2026',  '',      '',          '',        1100.0,  1100.0),

                # N-to-1: the sole credit is split proportionally over both debits
                ('MISC/2026/03/0001',                     '03/10/2026',  '',      '',          '',         660.0,   660.0),
                    (f'{exp} Operating expense',          '03/10/2026',  '',      pay,         '',         600.0,     0.0),
                    (f'{ast} Prepaid expense',            '03/10/2026',  '',      pay,         '',          60.0,     0.0),
                    (f'{pay} Supplier payable',           '03/10/2026',  '',      exp,         '',           0.0,   600.0),
                    (f'{pay} Supplier payable',           '03/10/2026',  '',      ast,         '',           0.0,    60.0),
                ('Total MISC/2026/03/0001',               '03/10/2026',  '',      '',          '',         660.0,   660.0),

                ('Total General Journal',                 '',            '',      '',          '',        2760.0,  2760.0),
            ],
            options,
        )

    @freeze_time('2026-04-01')
    def test_general_journal_report_many_to_many(self):
        """N-to-N move: label-matched pairs get their counterpart, the rest is grouped under 'Non-Counterparted Lines'."""
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.misc_journal.id,
            'date': '2026-01-10',
            'line_ids': [
                # 'Pair A' and 'Pair B' share label + equal amount on both sides → matched.
                # 'Unmatched D' and 'Unmatched C' have no counterpart with the same label → uncategorized.
                Command.create({'account_id': self.receivable.id, 'debit': 500.0, 'credit':   0.0, 'name': 'Pair A'}),
                Command.create({'account_id': self.assets.id,    'debit': 300.0, 'credit':   0.0, 'name': 'Pair B'}),
                Command.create({'account_id': self.payable.id,   'debit': 200.0, 'credit':   0.0, 'name': 'Unmatched D'}),
                Command.create({'account_id': self.revenue.id,   'debit':   0.0, 'credit': 500.0, 'name': 'Pair A'}),
                Command.create({'account_id': self.expense.id,   'debit':   0.0, 'credit': 300.0, 'name': 'Pair B'}),
                Command.create({'account_id': self.assets.id,    'debit':   0.0, 'credit': 200.0, 'name': 'Unmatched C'}),
            ],
        }).action_post()

        options = self._generate_options(self.general_journal_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev, exp, pay, ast = (
            self.receivable_disp, self.revenue_disp,
            self.expense_disp, self.payable_disp, self.assets_disp,
        )

        self.assertLinesValues(
            self.general_journal_report._get_lines(options),
            #   Name                                      Date           Partner  Counterpart  Currency    Debit    Credit
            [   0,                                        1,             2,       3,           4,          5,       6],
            [
                ('General Journal',                       '',            '',      '',          '',        1000.0,  1000.0),

                ('MISC/2026/01/0001',                     '01/10/2026',  '',      '',          '',        1000.0,  1000.0),
                    (f'{rcv} Pair A',                     '01/10/2026',  '',      rev,         '',         500.0,     0.0),
                    (f'{ast} Pair B',                     '01/10/2026',  '',      exp,         '',         300.0,     0.0),
                    (f'{rev} Pair A',                     '01/10/2026',  '',      rcv,         '',           0.0,   500.0),
                    (f'{exp} Pair B',                     '01/10/2026',  '',      ast,         '',           0.0,   300.0),
                    ('Non-Counterparted Lines',           '',            '',      '',          '',            '',      ''),
                        (f'{pay} Unmatched D',            '01/10/2026',  '',      '',          '',         200.0,     0.0),
                        (f'{ast} Unmatched C',            '01/10/2026',  '',      '',          '',           0.0,   200.0),
                ('Total MISC/2026/01/0001',               '01/10/2026',  '',      '',          '',        1000.0,  1000.0),

                ('Total General Journal',                 '',            '',      '',          '',        1000.0,  1000.0),
            ],
            options,
        )

    @freeze_time('2026-04-01')
    def test_general_journal_report_is_restricted_to_the_period(self):
        """Contrary to the general ledger, the journal has no opening balance: earlier entries are simply not listed."""
        self.env['account.move'].create([
            {
                'move_type': 'entry',
                'journal_id': self.misc_journal.id,
                'date': '2025-12-10',
                'line_ids': [
                    Command.create({'account_id': self.receivable.id, 'debit': 700.0, 'credit': 0.0, 'name': 'Previous year'}),
                    Command.create({'account_id': self.revenue.id, 'debit': 0.0, 'credit': 700.0, 'name': 'Previous year'}),
                ],
            },
            {
                'move_type': 'entry',
                'journal_id': self.misc_journal.id,
                'date': '2026-01-10',
                'line_ids': [
                    Command.create({'account_id': self.receivable.id, 'debit': 400.0, 'credit': 0.0, 'name': 'This period'}),
                    Command.create({'account_id': self.revenue.id, 'debit': 0.0, 'credit': 400.0, 'name': 'This period'}),
                ],
            },
        ]).action_post()

        options = self._generate_options(self.general_journal_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev = self.receivable_disp, self.revenue_disp

        self.assertLinesValues(
            self.general_journal_report._get_lines(options),
            #   Name                                      Date           Partner  Counterpart  Currency    Debit    Credit
            [   0,                                        1,             2,       3,           4,          5,       6],
            [
                ('General Journal',                       '',            '',      '',          '',         400.0,   400.0),

                ('MISC/2026/01/0001',                     '01/10/2026',  '',      '',          '',         400.0,   400.0),
                    (f'{rcv} This period',                '01/10/2026',  '',      rev,         '',         400.0,     0.0),
                    (f'{rev} This period',                '01/10/2026',  '',      rcv,         '',           0.0,   400.0),
                ('Total MISC/2026/01/0001',               '01/10/2026',  '',      '',          '',         400.0,   400.0),

                ('Total General Journal',                 '',            '',      '',          '',         400.0,   400.0),
            ],
            options,
        )

    @freeze_time('2026-04-01')
    def test_general_journal_report_foreign_currency(self):
        """An entry wholly in a foreign currency reports its debit side, and each of its items its own amount."""
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.misc_journal.id,
            'date': '2026-01-10',
            'line_ids': [
                Command.create({'account_id': self.assets.id,  'debit': 1100.0, 'credit':    0.0, 'name': 'Asset receipt',
                                'currency_id': self.other_currency.id, 'amount_currency':  2200.0}),
                Command.create({'account_id': self.revenue.id, 'debit':    0.0, 'credit': 1000.0, 'name': 'Revenue',
                                'currency_id': self.other_currency.id, 'amount_currency': -2000.0}),
                Command.create({'account_id': self.expense.id, 'debit':    0.0, 'credit':  100.0, 'name': 'Expense credit',
                                'currency_id': self.other_currency.id, 'amount_currency': -200.0}),
            ],
        }).action_post()

        options = self._generate_options(self.general_journal_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rev, exp, ast = self.revenue_disp, self.expense_disp, self.assets_disp

        self.assertLinesValues(
            self.general_journal_report._get_lines(options),
            #   Name                                      Date           Partner  Counterpart  Currency    Debit    Credit
            [   0,                                        1,             2,       3,           4,          5,       6],
            [
                ('General Journal',                       '',            '',      '',          '',        1100.0,  1100.0),

                # The entry is in one currency: its debit side, 2200.0, is the counterpart
                # in currency of the 1100.0 of the Debit and Credit columns.
                ('MISC/2026/01/0001',                     '01/10/2026',  '',      '',        2200.0,      1100.0,  1100.0),
                    # The sole debit is split over both credits, in currency as well.
                    (f'{ast} Asset receipt',              '01/10/2026',  '',      rev,       2000.0,      1000.0,     0.0),
                    (f'{ast} Asset receipt',              '01/10/2026',  '',      exp,        200.0,       100.0,     0.0),
                    (f'{rev} Revenue',                    '01/10/2026',  '',      ast,      -2000.0,         0.0,  1000.0),
                    (f'{exp} Expense credit',             '01/10/2026',  '',      ast,       -200.0,         0.0,   100.0),
                ('Total MISC/2026/01/0001',               '01/10/2026',  '',      '',        2200.0,      1100.0,  1100.0),

                ('Total General Journal',                 '',            '',      '',          '',        1100.0,  1100.0),
            ],
            options,
            currency_map={4: {'currency': self.other_currency}},
        )

    @freeze_time('2026-04-01')
    def test_general_journal_report_mixed_currencies(self):
        """An entry mixing currencies reports none of them, and the items in the company one report nothing."""
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.misc_journal.id,
            'date': '2026-01-10',
            'line_ids': [
                Command.create({'account_id': self.receivable.id, 'debit': 500.0, 'credit':   0.0, 'name': 'Customer receivable',
                                'currency_id': self.other_currency.id, 'amount_currency': 1000.0}),
                Command.create({'account_id': self.revenue.id,    'debit':   0.0, 'credit': 500.0, 'name': 'Revenue'}),
            ],
        }).action_post()

        options = self._generate_options(self.general_journal_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev = self.receivable_disp, self.revenue_disp

        self.assertLinesValues(
            self.general_journal_report._get_lines(options),
            #   Name                                      Date           Partner  Counterpart  Currency    Debit    Credit
            [   0,                                        1,             2,       3,           4,          5,       6],
            [
                ('General Journal',                       '',            '',      '',          '',         500.0,   500.0),

                # Nothing in the Currency column of the entry: its two items are not in the same one.
                ('MISC/2026/01/0001',                     '01/10/2026',  '',      '',          '',         500.0,   500.0),
                    (f'{rcv} Customer receivable',        '01/10/2026',  '',      rev,       1000.0,        500.0,     0.0),
                    (f'{rev} Revenue',                    '01/10/2026',  '',      rcv,         '',           0.0,   500.0),
                ('Total MISC/2026/01/0001',               '01/10/2026',  '',      '',          '',         500.0,   500.0),

                ('Total General Journal',                 '',            '',      '',          '',         500.0,   500.0),
            ],
            options,
            currency_map={4: {'currency': self.other_currency}},
        )
