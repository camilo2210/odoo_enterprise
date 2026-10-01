# ruff: noqa: E241, E201
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nVnGeneralLedger(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('vn')
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_a.write({
            'country_id': cls.env.ref('base.vn').id,
            'vat': '0123456789',
        })
        cls.partner_b.write({
            'country_id': cls.env.ref('base.vn').id,
            'vat': '9876543210',
        })

        cls.general_ledger_report = cls.env.ref('l10n_vn_reports.general_ledger_report_l10n_vn')

        cls.receivable = cls.company_data['default_account_receivable']
        cls.revenue = cls.company_data['default_account_revenue']
        cls.expense = cls.company_data['default_account_expense']
        cls.payable = cls.company_data['default_account_payable']
        cls.assets = cls.company_data['default_account_assets']
        cls.misc_journal = cls.company_data['default_journal_misc']
        cls.sale_journal = cls.company_data['default_journal_sale']
        cls.tax_closing_journal = cls.company_data['company']._get_tax_closing_journal()

        cls.receivable_disp = f"{cls.receivable.code} {cls.receivable.name}"
        cls.revenue_disp = f"{cls.revenue.code} {cls.revenue.name}"
        cls.expense_disp = f"{cls.expense.code} {cls.expense.name}"
        cls.payable_disp = f"{cls.payable.code} {cls.payable.name}"
        cls.assets_disp = f"{cls.assets.code} {cls.assets.name}"

    @freeze_time('2026-04-01')
    def test_general_ledger_report(self):
        """Normal moves: 1-to-1, 1-to-N, and N-to-1 — counterpart correctly assigned and amounts proportionally split."""
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

        options = self._generate_options(self.general_ledger_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev, exp, pay, ast = (
            self.receivable_disp, self.revenue_disp,
            self.expense_disp, self.payable_disp, self.assets_disp,
        )

        self.assertLinesValues(
            self.general_ledger_report._get_lines(options),
            #   Name                                               Date           Partner  Counterpart  Currency    Debit    Credit  Bal Debit  Bal Credit
            [   0,                                                 1,             2,       3,           4,          5,       6,      7,         8],
            [
                ('General Ledger',                                 '',            '',      '',          '',        2760.0,  2760.0,      0.0,       0.0),

                # 131 — Move 1: 1-to-1  (DR 1 000 ↔ Revenue)
                (rcv,                                              '',            '',      '',          '',        1000.0,     0.0,   1000.0,       0.0),
                    ('MISC/2026/01/0001 Customer receivable',      '01/10/2026',  '',      rev,         '',        1000.0,     0.0,   1000.0,       0.0),
                    ('Total for Period',                           '',            '',      '',          '',        1000.0,     0.0,       '',        ''),
                (f'Total {rcv}',                                   '',            '',      '',          '',        1000.0,     0.0,   1000.0,       0.0),

                # 211 — Move 2: 1-to-N split (DR 1 000→Revenue, DR 100→Expense), Move 3: N-to-1 (DR 60→Payable)
                (ast,                                              '',            '',      '',          '',        1160.0,     0.0,   1160.0,       0.0),
                    ('MISC/2026/02/0001 Asset receipt',            '02/10/2026',  '',      rev,         '',        1000.0,     0.0,   1000.0,       0.0),
                    ('MISC/2026/02/0001 Asset receipt',            '02/10/2026',  '',      exp,         '',         100.0,     0.0,   1100.0,       0.0),
                    ('MISC/2026/03/0001 Prepaid expense',          '03/10/2026',  '',      pay,         '',          60.0,     0.0,   1160.0,       0.0),
                    ('Total for Period',                           '',            '',      '',          '',        1160.0,     0.0,       '',        ''),
                (f'Total {ast}',                                   '',            '',      '',          '',        1160.0,     0.0,   1160.0,       0.0),

                # 331 — Move 3: N-to-1 split (CR 600←Expense, CR 60←Assets)
                (pay,                                              '',            '',      '',          '',           0.0,   660.0,      0.0,     660.0),
                    ('MISC/2026/03/0001 Supplier payable',         '03/10/2026',  '',      exp,         '',           0.0,   600.0,      0.0,     600.0),
                    ('MISC/2026/03/0001 Supplier payable',         '03/10/2026',  '',      ast,         '',           0.0,    60.0,      0.0,     660.0),
                    ('Total for Period',                           '',            '',      '',          '',           0.0,   660.0,       '',        ''),
                (f'Total {pay}',                                   '',            '',      '',          '',           0.0,   660.0,      0.0,     660.0),

                # 511 — Move 1: 1-to-1 (CR 1 000 ↔ Receivable), Move 2: 1-to-N (CR 1 000 ↔ Assets)
                (rev,                                              '',            '',      '',          '',           0.0,  2000.0,      0.0,    2000.0),
                    ('MISC/2026/01/0001 Revenue',                  '01/10/2026',  '',      rcv,         '',           0.0,  1000.0,      0.0,    1000.0),
                    ('MISC/2026/02/0001 Revenue',                  '02/10/2026',  '',      ast,         '',           0.0,  1000.0,      0.0,    2000.0),
                    ('Total for Period',                           '',            '',      '',          '',           0.0,  2000.0,       '',        ''),
                (f'Total {rev}',                                   '',            '',      '',          '',           0.0,  2000.0,      0.0,    2000.0),

                # 641 — Move 2: 1-to-N (CR 100 ↔ Assets), Move 3: N-to-1 (DR 600 ↔ Payable)
                (exp,                                              '',            '',      '',          '',         600.0,   100.0,    500.0,       0.0),
                    ('MISC/2026/02/0001 Expense credit',           '02/10/2026',  '',      ast,         '',           0.0,   100.0,      0.0,     100.0),
                    ('MISC/2026/03/0001 Operating expense',        '03/10/2026',  '',      pay,         '',         600.0,     0.0,    500.0,       0.0),
                    ('Total for Period',                           '',            '',      '',          '',         600.0,   100.0,       '',        ''),
                (f'Total {exp}',                                   '',            '',      '',          '',         600.0,   100.0,    500.0,       0.0),

                ('Total General Ledger',                           '',            '',      '',          '',        2760.0,  2760.0,      0.0,       0.0),
            ],
            options,
        )

    @freeze_time('2026-04-01')
    def test_general_ledger_report_many_to_many(self):
        """N-to-N move: label-matched pairs get their counterpart; lines without a matching label are grouped under 'Non-Counterparted Lines'."""
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

        options = self._generate_options(self.general_ledger_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev, exp, pay, ast = (
            self.receivable_disp, self.revenue_disp,
            self.expense_disp, self.payable_disp, self.assets_disp,
        )

        self.assertLinesValues(
            self.general_ledger_report._get_lines(options),
            #   Name                                           Date           Partner  Counterpart  Currency  Debit   Credit  Bal Debit  Bal Credit
            [   0,                                             1,             2,       3,           4,        5,      6,      7,         8],
            [
                ('General Ledger',                             '',            '',      '',          '',      1000.0, 1000.0,      0.0,       0.0),

                # 131 — Pair A: DR 500 ↔ Revenue (label-matched)
                (rcv,                                          '',            '',      '',          '',       500.0,    0.0,    500.0,       0.0),
                    ('MISC/2026/01/0001 Pair A',               '01/10/2026',  '',      rev,         '',       500.0,    0.0,    500.0,       0.0),
                    ('Total for Period',                       '',            '',      '',          '',       500.0,    0.0,       '',        ''),
                (f'Total {rcv}',                               '',            '',      '',          '',       500.0,    0.0,    500.0,       0.0),

                # 211 — Pair B: DR 300 ↔ Expense (matched); Unmatched C: CR 200 → uncategorized
                (ast,                                          '',            '',      '',          '',       300.0,  200.0,    100.0,       0.0),
                    ('MISC/2026/01/0001 Pair B',               '01/10/2026',  '',      exp,         '',       300.0,    0.0,    300.0,       0.0),
                    ('Non-Counterparted Lines',                '',            '',      '',          '',          '',     '',       '',         ''),
                        ('MISC/2026/01/0001 Unmatched C',      '01/10/2026',  '',      '',          '',         0.0,  200.0,    100.0,       0.0),
                    ('Total for Period',                       '',            '',      '',          '',       300.0,  200.0,       '',        ''),
                (f'Total {ast}',                               '',            '',      '',          '',       300.0,  200.0,    100.0,       0.0),

                # 331 — Unmatched D: DR 200 → uncategorized (no label match on credit side)
                (pay,                                          '',            '',      '',          '',       200.0,    0.0,    200.0,       0.0),
                    ('Non-Counterparted Lines',                '',            '',      '',          '',          '',     '',       '',         ''),
                        ('MISC/2026/01/0001 Unmatched D',      '01/10/2026',  '',      '',          '',       200.0,    0.0,    200.0,       0.0),
                    ('Total for Period',                       '',            '',      '',          '',       200.0,    0.0,       '',        ''),
                (f'Total {pay}',                               '',            '',      '',          '',       200.0,    0.0,    200.0,       0.0),

                # 511 — Pair A: CR 500 ↔ Receivable (label-matched)
                (rev,                                          '',            '',      '',          '',         0.0,  500.0,      0.0,     500.0),
                    ('MISC/2026/01/0001 Pair A',               '01/10/2026',  '',      rcv,         '',         0.0,  500.0,      0.0,     500.0),
                    ('Total for Period',                       '',            '',      '',          '',         0.0,  500.0,       '',        ''),
                (f'Total {rev}',                               '',            '',      '',          '',         0.0,  500.0,      0.0,     500.0),

                # 641 — Pair B: CR 300 ↔ Assets (label-matched)
                (exp,                                          '',            '',      '',          '',         0.0,  300.0,      0.0,     300.0),
                    ('MISC/2026/01/0001 Pair B',               '01/10/2026',  '',      ast,         '',         0.0,  300.0,      0.0,     300.0),
                    ('Total for Period',                       '',            '',      '',          '',         0.0,  300.0,       '',        ''),
                (f'Total {exp}',                               '',            '',      '',          '',         0.0,  300.0,      0.0,     300.0),

                ('Total General Ledger',                       '',            '',      '',          '',      1000.0, 1000.0,      0.0,       0.0),
            ],
            options,
        )

    @freeze_time('2026-04-01')
    def test_general_ledger_report_sale_purchase_journal(self):
        """Sale/purchase journal: 1-to-1 label+amount pairing first, then proportional split for remainder; running balance columns are correct."""
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.sale_journal.id,
            'date': '2026-01-15',
            'line_ids': [
                # 'Pair A': same label+equal amount on both sides → step-1 1-to-1 match.
                # 'Split': sole remaining debit after step 1 → step-2 proportional split
                #          across the two remaining credit lines.
                Command.create({'account_id': self.receivable.id, 'debit': 500.0, 'credit':   0.0, 'name': 'Pair A'}),
                Command.create({'account_id': self.receivable.id, 'debit': 900.0, 'credit':   0.0, 'name': 'Split'}),
                Command.create({'account_id': self.revenue.id,   'debit':   0.0, 'credit': 500.0, 'name': 'Pair A'}),
                Command.create({'account_id': self.revenue.id,   'debit':   0.0, 'credit': 600.0, 'name': 'Remainder 1'}),
                Command.create({'account_id': self.expense.id,   'debit':   0.0, 'credit': 300.0, 'name': 'Remainder 2'}),
            ],
        }).action_post()

        options = self._generate_options(self.general_ledger_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev, exp = (
            self.receivable_disp, self.revenue_disp, self.expense_disp,
        )

        self.assertLinesValues(
            self.general_ledger_report._get_lines(options),
            #   Name                                             Date           Partner  Counterpart  Currency  Debit    Credit  Bal Debit  Bal Credit
            [   0,                                               1,             2,       3,           4,        5,       6,      7,         8],
            [
                ('General Ledger',                               '',            '',      '',          '',      1400.0, 1400.0,      0.0,       0.0),

                # 131 — 'Pair A': step-1 matched to Revenue; 'Split': step-2 sole DR split
                #        proportionally across Revenue (600) and Expense (300).
                (rcv,                                            '',            '',      '',          '',      1400.0,    0.0,   1400.0,       0.0),
                    ('INV/2026/00001 Pair A',                    '01/15/2026',  '',      rev,         '',       500.0,    0.0,    500.0,       0.0),
                    ('INV/2026/00001 Split',                     '01/15/2026',  '',      rev,         '',       600.0,    0.0,   1100.0,       0.0),
                    ('INV/2026/00001 Split',                     '01/15/2026',  '',      exp,         '',       300.0,    0.0,   1400.0,       0.0),
                    ('Total for Period',                         '',            '',      '',          '',      1400.0,    0.0,       '',        ''),
                (f'Total {rcv}',                                 '',            '',      '',          '',      1400.0,    0.0,   1400.0,       0.0),

                # 511 — 'Pair A': step-1 matched to Receivable; 'Remainder 1': step-2 counterpart.
                (rev,                                            '',            '',      '',          '',         0.0, 1100.0,      0.0,    1100.0),
                    ('INV/2026/00001 Pair A',                    '01/15/2026',  '',      rcv,         '',         0.0,  500.0,      0.0,     500.0),
                    ('INV/2026/00001 Remainder 1',               '01/15/2026',  '',      rcv,         '',         0.0,  600.0,      0.0,    1100.0),
                    ('Total for Period',                         '',            '',      '',          '',         0.0, 1100.0,       '',        ''),
                (f'Total {rev}',                                 '',            '',      '',          '',         0.0, 1100.0,      0.0,    1100.0),

                # 641 — 'Remainder 2': step-2 counterpart to the split debit.
                (exp,                                            '',            '',      '',          '',         0.0,  300.0,      0.0,     300.0),
                    ('INV/2026/00001 Remainder 2',               '01/15/2026',  '',      rcv,         '',         0.0,  300.0,      0.0,     300.0),
                    ('Total for Period',                         '',            '',      '',          '',         0.0,  300.0,       '',        ''),
                (f'Total {exp}',                                 '',            '',      '',          '',         0.0,  300.0,      0.0,     300.0),

                ('Total General Ledger',                         '',            '',      '',          '',      1400.0, 1400.0,      0.0,       0.0),
            ],
            options,
        )

    @freeze_time('2026-04-01')
    def test_general_ledger_report_tax_closing_journal(self):
        """Tax-closing move: lines grouped by account, proportionally split across counterpart accounts, move name used as label."""
        # A tax-closing move is identified by having closing_return_id set.
        # Create a minimal account.return so the field can be populated.
        return_type = self.env['account.return.type'].create({'name': 'Test Type'})
        account_return = self.env['account.return'].create({
            'name': 'Q1 2026 VAT',
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
            'type_id': return_type.id,
            'company_id': self.company_data['company'].id,
        })

        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.tax_closing_journal.id,
            'date': '2026-01-31',
            'closing_return_id': account_return.id,
            'line_ids': [
                # Debit: same account_id (receivable), two lines with different labels → 1 debit group.
                # Credit: three different account_ids with different amounts → 3 credit groups.
                # The single debit group is split proportionally across the 3 credit accounts.
                # Line labels are ignored; the move name is used as the row label.
                Command.create({'account_id': self.receivable.id, 'debit': 600.0, 'credit':   0.0, 'name': 'VAT Refund'}),
                Command.create({'account_id': self.receivable.id, 'debit': 400.0, 'credit':   0.0, 'name': 'VAT Purchase'}),
                Command.create({'account_id': self.revenue.id,   'debit':   0.0, 'credit': 500.0, 'name': 'VAT Sales'}),
                Command.create({'account_id': self.payable.id,   'debit':   0.0, 'credit': 300.0, 'name': 'VAT Payable'}),
                Command.create({'account_id': self.assets.id,    'debit':   0.0, 'credit': 200.0, 'name': 'VAT Asset'}),
            ],
        }).action_post()

        options = self._generate_options(self.general_ledger_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev, pay, ast = (
            self.receivable_disp, self.revenue_disp,
            self.payable_disp, self.assets_disp,
        )

        self.assertLinesValues(
            self.general_ledger_report._get_lines(options),
            #   Name                                     Date           Partner  Counterpart  Currency  Debit   Credit  Bal Debit  Bal Credit
            [   0,                                       1,             2,       3,           4,        5,      6,      7,         8],
            [
                ('General Ledger',                       '',            '',      '',          '',      1000.0, 1000.0,      0.0,       0.0),

                # 131 — Receivable: two AMLs (DR 600 + DR 400) each split independently
                #        across 3 credit accounts by proportional raw-amount ratios.
                #        DR 600: 600*500/1000=300→Rev, 600*300/1000=180→Pay, rem=120→Ast
                #        DR 400: 400*500/1000=200→Rev, 400*300/1000=120→Pay, rem= 80→Ast
                (rcv,                                    '',            '',      '',          '',      1000.0,    0.0,   1000.0,       0.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      rev,         '',       300.0,    0.0,    300.0,       0.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      pay,         '',       180.0,    0.0,    480.0,       0.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      ast,         '',       120.0,    0.0,    600.0,       0.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      rev,         '',       200.0,    0.0,    800.0,       0.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      pay,         '',       120.0,    0.0,    920.0,       0.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      ast,         '',        80.0,    0.0,   1000.0,       0.0),
                    ('Total for Period',                 '',            '',      '',          '',      1000.0,    0.0,       '',        ''),
                (f'Total {rcv}',                         '',            '',      '',          '',      1000.0,    0.0,   1000.0,       0.0),

                # 211 — Assets CR 200: sole debit group is receivable → counterpart = receivable
                (ast,                                    '',            '',      '',          '',         0.0,  200.0,      0.0,     200.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      rcv,         '',         0.0,  200.0,      0.0,     200.0),
                    ('Total for Period',                 '',            '',      '',          '',         0.0,  200.0,       '',        ''),
                (f'Total {ast}',                         '',            '',      '',          '',         0.0,  200.0,      0.0,     200.0),

                # 331 — Payable CR 300: counterpart = receivable
                (pay,                                    '',            '',      '',          '',         0.0,  300.0,      0.0,     300.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      rcv,         '',         0.0,  300.0,      0.0,     300.0),
                    ('Total for Period',                 '',            '',      '',          '',         0.0,  300.0,       '',        ''),
                (f'Total {pay}',                         '',            '',      '',          '',         0.0,  300.0,      0.0,     300.0),

                # 511 — Revenue CR 500: counterpart = receivable
                (rev,                                    '',            '',      '',          '',         0.0,  500.0,      0.0,     500.0),
                    ('TAX/2026/01/0001',                 '01/31/2026',  '',      rcv,         '',         0.0,  500.0,      0.0,     500.0),
                    ('Total for Period',                 '',            '',      '',          '',         0.0,  500.0,       '',        ''),
                (f'Total {rev}',                         '',            '',      '',          '',         0.0,  500.0,      0.0,     500.0),

                ('Total General Ledger',                 '',            '',      '',          '',      1000.0, 1000.0,      0.0,       0.0),
            ],
            options,
        )

        # -----------------------------------------------------------------------
        # Distinct accounts: BOTH debit and credit sides have >1 distinct account
        # groups — proportional distribution is arbitrary, so the report falls
        # back to uncategorized and all lines appear under Non-Counterparted Lines.
        # -----------------------------------------------------------------------
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.tax_closing_journal.id,
            'date': '2026-02-28',
            'closing_return_id': account_return.id,
            'line_ids': [
                # Two debit accounts AND three credit accounts: both sides are
                # "distinct" (len > 1), so no side can be reduced to a single
                # representative and the split would be arbitrary.
                Command.create({'account_id': self.assets.id,      'debit': 100.0, 'credit':   0.0, 'name': 'Input VAT'}),
                Command.create({'account_id': self.expense.id,     'debit': 400.0, 'credit':   0.0, 'name': 'Output VAT'}),
                Command.create({'account_id': self.revenue.id,     'debit':   0.0, 'credit': 250.0, 'name': 'VAT Settlement A'}),
                Command.create({'account_id': self.payable.id,     'debit':   0.0, 'credit': 150.0, 'name': 'VAT Settlement B'}),
                Command.create({'account_id': self.receivable.id,  'debit':   0.0, 'credit': 100.0, 'name': 'VAT Settlement C'}),
            ],
        }).action_post()

        rcv, rev, exp, pay, ast = (
            self.receivable_disp, self.revenue_disp,
            self.expense_disp, self.payable_disp, self.assets_disp,
        )

        options_distinct = self._generate_options(
            self.general_ledger_report, '2026-02-01', '2026-02-28', {'unfold_all': True},
        )

        self.assertLinesValues(
            self.general_ledger_report._get_lines(options_distinct),
            #   Name                                     Date           Partner  Counterpart  Currency  Debit   Credit  Bal Debit  Bal Credit
            [   0,                                       1,             2,       3,           4,        5,      6,      7,         8],
            [
                ('General Ledger',                       '',            '',      '',          '',      1500.0, 1500.0,      0.0,       0.0),

                # 131 — receivable CR 100: uncategorized; initial balance DR 1000 carried from Jan move
                # account header debit/credit include initial (DR 1000) + period (CR 100)
                (rcv,                                    '',            '',      '',          '',      1000.0,  100.0,    900.0,       0.0),
                    ('Initial Balance',                  '',            '',      '',          '',      1000.0,    0.0,   1000.0,       0.0),
                    ('Non-Counterparted Lines',          '',            '',      '',          '',          '',     '',       '',        ''),
                        ('TAX/2026/02/0001',             '02/28/2026',  '',      '',          '',         0.0,  100.0,    900.0,       0.0),
                    ('Total for Period',                 '',            '',      '',          '',         0.0,  100.0,       '',        ''),
                (f'Total {rcv}',                         '',            '',      '',          '',      1000.0,  100.0,    900.0,       0.0),

                # 211 — assets DR 100: uncategorized; initial balance CR 200 carried from Jan move
                # account header: initial (CR 200) + period (DR 100)
                (ast,                                    '',            '',      '',          '',       100.0,  200.0,      0.0,     100.0),
                    ('Initial Balance',                  '',            '',      '',          '',         0.0,  200.0,      0.0,     200.0),
                    ('Non-Counterparted Lines',          '',            '',      '',          '',          '',     '',       '',        ''),
                        ('TAX/2026/02/0001',             '02/28/2026',  '',      '',          '',       100.0,    0.0,      0.0,     100.0),
                    ('Total for Period',                 '',            '',      '',          '',       100.0,    0.0,       '',        ''),
                (f'Total {ast}',                         '',            '',      '',          '',       100.0,  200.0,      0.0,     100.0),

                # 331 — payable CR 150: uncategorized; initial balance CR 300 carried from Jan move
                # account header: initial (CR 300) + period (CR 150) = CR 450
                (pay,                                    '',            '',      '',          '',         0.0,  450.0,      0.0,     450.0),
                    ('Initial Balance',                  '',            '',      '',          '',         0.0,  300.0,      0.0,     300.0),
                    ('Non-Counterparted Lines',          '',            '',      '',          '',          '',     '',       '',        ''),
                        ('TAX/2026/02/0001',             '02/28/2026',  '',      '',          '',         0.0,  150.0,      0.0,     450.0),
                    ('Total for Period',                 '',            '',      '',          '',         0.0,  150.0,       '',        ''),
                (f'Total {pay}',                         '',            '',      '',          '',         0.0,  450.0,      0.0,     450.0),

                # 511 — revenue CR 250: uncategorized; initial balance CR 500 carried from Jan move
                # account header: initial (CR 500) + period (CR 250) = CR 750
                (rev,                                    '',            '',      '',          '',         0.0,  750.0,      0.0,     750.0),
                    ('Initial Balance',                  '',            '',      '',          '',         0.0,  500.0,      0.0,     500.0),
                    ('Non-Counterparted Lines',          '',            '',      '',          '',          '',     '',       '',        ''),
                        ('TAX/2026/02/0001',             '02/28/2026',  '',      '',          '',         0.0,  250.0,      0.0,     750.0),
                    ('Total for Period',                 '',            '',      '',          '',         0.0,  250.0,       '',        ''),
                (f'Total {rev}',                         '',            '',      '',          '',         0.0,  750.0,      0.0,     750.0),

                # 641 — expense DR 400: uncategorized; no prior entries so no initial balance row
                (exp,                                    '',            '',      '',          '',       400.0,    0.0,    400.0,       0.0),
                    ('Non-Counterparted Lines',          '',            '',      '',          '',          '',     '',       '',        ''),
                        ('TAX/2026/02/0001',             '02/28/2026',  '',      '',          '',       400.0,    0.0,    400.0,       0.0),
                    ('Total for Period',                 '',            '',      '',          '',       400.0,    0.0,       '',        ''),
                (f'Total {exp}',                         '',            '',      '',          '',       400.0,    0.0,    400.0,       0.0),

                ('Total General Ledger',                 '',            '',      '',          '',      1500.0, 1500.0,      0.0,       0.0),
            ],
            options_distinct,
        )

    @freeze_time('2026-04-01')
    def test_general_ledger_report_multi_currency(self):
        """Each journal item shows its own amount in currency, and nothing when it is in the company one."""
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.misc_journal.id,
            'date': '2026-01-10',
            'line_ids': [
                Command.create({'account_id': self.receivable.id, 'debit': 500.0, 'credit':   0.0, 'name': 'Customer receivable',
                                'currency_id': self.other_currency.id, 'amount_currency':  1000.0}),
                Command.create({'account_id': self.revenue.id,    'debit':   0.0, 'credit': 500.0, 'name': 'Revenue'}),
            ],
        }).action_post()

        options = self._generate_options(self.general_ledger_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev = self.receivable_disp, self.revenue_disp

        self.assertLinesValues(
            self.general_ledger_report._get_lines(options),
            #   Name                                            Date           Partner  Counterpart  Currency  Debit   Credit  Bal. Debit  Bal. Credit
            [   0,                                              1,             2,       3,           4,        5,      6,      7,          8],
            [
                ('General Ledger',                                        '',      '',          '',       '',  500.0,  500.0,        0.0,         0.0),

                (rcv,                                                     '',      '',          '',       '',  500.0,    0.0,      500.0,         0.0),
                    ('MISC/2026/01/0001 Customer receivable',   '01/10/2026',      '',         rev,   1000.0,  500.0,    0.0,      500.0,         0.0),
                    ('Total for Period',                                  '',      '',          '',       '',  500.0,    0.0,         '',          ''),
                (f'Total {rcv}',                                          '',      '',          '',       '',  500.0,    0.0,      500.0,         0.0),

                (rev,                                                     '',      '',          '',       '',    0.0,  500.0,        0.0,       500.0),
                    ('MISC/2026/01/0001 Revenue',               '01/10/2026',      '',         rcv,       '',    0.0,  500.0,        0.0,       500.0),
                    ('Total for Period',                                  '',      '',          '',       '',    0.0,  500.0,         '',          ''),
                (f'Total {rev}',                                          '',      '',          '',       '',    0.0,  500.0,        0.0,       500.0),

                ('Total General Ledger',                                  '',      '',          '',       '',  500.0,  500.0,        0.0,         0.0),
            ],
            options,
            currency_map={4: {'currency': self.other_currency}},
        )

    @freeze_time('2026-04-01')
    def test_general_ledger_report_display_type_lines(self):
        """Section/note lines (display_type set, no account, zero balance) must be
        ignored by the counterpart matching and absent from the report: a plain
        1-to-1 move keeps its counterpart even when decorated with them."""
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.misc_journal.id,
            'date': '2026-01-10',
            'line_ids': [
                # Non-accounting lines interleaved with the real journal items; they
                # carry no account/balance and must not reach _compute_move_counterparts.
                Command.create({'display_type': 'line_section', 'name': 'Section header'}),
                Command.create({'account_id': self.receivable.id, 'debit': 1000.0, 'credit':    0.0, 'name': 'Customer receivable'}),
                Command.create({'display_type': 'line_note',    'name': 'Some note'}),
                Command.create({'account_id': self.revenue.id,   'debit':    0.0, 'credit': 1000.0, 'name': 'Revenue'}),
            ],
        }).action_post()

        options = self._generate_options(self.general_ledger_report, '2026-01-01', '2026-03-31', {'unfold_all': True})

        rcv, rev = self.receivable_disp, self.revenue_disp

        self.assertLinesValues(
            self.general_ledger_report._get_lines(options),
            #   Name                                          Date           Partner  Counterpart  Currency  Debit    Credit  Bal Debit  Bal Credit
            [   0,                                            1,             2,       3,           4,        5,       6,      7,         8],
            [
                ('General Ledger',                            '',            '',      '',          '',      1000.0, 1000.0,      0.0,       0.0),

                # 131 — DR 1 000 ↔ Revenue (section/note lines neither appear nor change the match)
                (rcv,                                         '',            '',      '',          '',      1000.0,    0.0,   1000.0,       0.0),
                    ('MISC/2026/01/0001 Customer receivable', '01/10/2026',  '',      rev,         '',      1000.0,    0.0,   1000.0,       0.0),
                    ('Total for Period',                      '',            '',      '',          '',      1000.0,    0.0,       '',        ''),
                (f'Total {rcv}',                              '',            '',      '',          '',      1000.0,    0.0,   1000.0,       0.0),

                # 511 — CR 1 000 ↔ Receivable
                (rev,                                         '',            '',      '',          '',         0.0, 1000.0,      0.0,    1000.0),
                    ('MISC/2026/01/0001 Revenue',             '01/10/2026',  '',      rcv,         '',         0.0, 1000.0,      0.0,    1000.0),
                    ('Total for Period',                      '',            '',      '',          '',         0.0, 1000.0,       '',        ''),
                (f'Total {rev}',                              '',            '',      '',          '',         0.0, 1000.0,      0.0,    1000.0),

                ('Total General Ledger',                      '',            '',      '',          '',      1000.0, 1000.0,      0.0,       0.0),
            ],
            options,
        )
