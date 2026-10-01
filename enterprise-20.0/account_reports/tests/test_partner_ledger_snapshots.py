# pylint: disable=C0326
from datetime import date

from .common import TestAccountReportsCommon

from odoo import fields
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPartnerLedgerSnapshots(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        for company in cls.env.companies:
            assert not company.hard_lock_date  # Make sure we crash if the common test setup changes in the future
            company.fiscalyear_lock_date = None
            company.tax_lock_date = None

        # The snapshots' serialized options embed company-dependent values (e.g. the exchange journals domain);
        # like the cron, evaluate everything on a single company.
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company_data['company'].ids))

        # Only the partner ledger should generate snapshots in these tests
        cls.report = cls.env.ref('account_reports.partner_ledger_report')
        cls.env['account.report'].search([('id', '!=', cls.report.id)]).enable_snapshots = False

        # Entries in 2016, forming the initial balances of the 2017 report
        cls.move_2016_a = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-01-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 100.0, 'credit': 0.0,   'name': '2016_a_1', 'account_id': cls.company_data['default_account_receivable'].id, 'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,   'credit': 300.0, 'name': '2016_a_2', 'account_id': cls.company_data['default_account_receivable'].id, 'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 200.0, 'credit': 0.0,   'name': '2016_a_3', 'account_id': cls.company_data['default_account_revenue'].id}),
            ],
        })
        # A trade line without partner, ending up in the 'Unknown Partner' group
        cls.move_2016_b = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-06-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 0.0,   'credit': 150.0, 'name': '2016_b_1', 'account_id': cls.company_data['default_account_receivable'].id}),
                (0, 0, {'debit': 150.0, 'credit': 0.0,   'name': '2016_b_2', 'account_id': cls.company_data['default_account_revenue'].id}),
            ],
        })
        # Entry in 2017, inside the reported period
        cls.move_2017 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2017-01-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 1000.0, 'credit': 0.0,    'name': '2017_1', 'account_id': cls.company_data['default_account_receivable'].id, 'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,    'credit': 1000.0, 'name': '2017_2', 'account_id': cls.company_data['default_account_revenue'].id}),
            ],
        })
        (cls.move_2016_a + cls.move_2016_b + cls.move_2017).action_post()

        cls._cleanup_snapshot_cron_triggers()

    def _get_partner_ledger_snapshots(self):
        return self.env['account.report.snapshot'].sudo().search([('report_id', '=', self.report.id)]).sorted(lambda snapshot: snapshot.groupby or '')

    def test_partner_ledger_snapshot_lifecycle(self):
        """ The partner ledger's initial balances must be snapshotted per partner when a lock date is set, and give
        the exact same report content as a full computation.
        """
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')

        # Without any snapshot
        self.assertFalse(self._get_partner_ledger_snapshots())
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                          Balance
            [   0,                            9],
            [
                ('Partner Ledger',            650.0),
                ('partner_a',                1100.0),
                ('partner_b',                -300.0),
                ('Unknown Partner',          -150.0),
                ('Total Partner Ledger',      650.0),
            ],
            options,
        )

        # Snapshots are created at the lock date, for both the line totals and its first groupby level
        self.env.company.fiscalyear_lock_date = '2016-12-31'
        self._run_snapshot_crons()

        snapshots = self._get_partner_ledger_snapshots()
        self.assertEqual(
            [(snapshot.groupby, snapshot.date, snapshot.engine_func) for snapshot in snapshots],
            [
                (False, date(2016, 12, 31), '_report_engine_partner_ledger_initial_balance'),
                ('partner_id', date(2016, 12, 31), '_report_engine_partner_ledger_initial_balance'),
            ],
        )

        # Rendering now goes through the snapshots, and must give the exact same values as the full computation
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                          Balance
            [   0,                            9],
            [
                ('Partner Ledger',            650.0),
                ('partner_a',                1100.0),
                ('partner_b',                -300.0),
                ('Unknown Partner',          -150.0),
                ('Total Partner Ledger',      650.0),
            ],
            options,
        )

        # Corrupting partner_a's snapshot must move its reported balance, proving the initial balance really comes
        # from the snapshot instead of being recomputed.
        partner_snapshot = snapshots.filtered(lambda snapshot: snapshot.groupby == 'partner_id')
        partner_snapshot.result = {
            expression_ids: [
                [grouping_key, {**group_values, 'init_balance': group_values['init_balance'] + 11.0 if grouping_key == self.partner_a.id else group_values['init_balance']}]
                for grouping_key, group_values in formula_result
            ]
            for expression_ids, formula_result in partner_snapshot.result.items()
        }
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                          Balance
            [   0,                            9],
            [
                ('Partner Ledger',            650.0),
                ('partner_a',                1111.0),
                ('partner_b',                -300.0),
                ('Unknown Partner',          -150.0),
                ('Total Partner Ledger',      650.0),
            ],
            options,
        )

        # Lowering the lock date garbage collects the corrupted snapshots (new ones are regenerated at the new
        # lock date, covering an empty period), and the correct values come back
        self.env.company.fiscalyear_lock_date = '2015-12-31'
        self._run_snapshot_crons()
        self.assertTrue(all(snapshot.date == date(2015, 12, 31) for snapshot in self._get_partner_ledger_snapshots()))
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                          Balance
            [   0,                            9],
            [
                ('Partner Ledger',            650.0),
                ('partner_a',                1100.0),
                ('partner_b',                -300.0),
                ('Unknown Partner',          -150.0),
                ('Total Partner Ledger',      650.0),
            ],
            options,
        )

    def test_partner_ledger_snapshot_no_partner_reconciled(self):
        """ Reconciling a partner-less line with a line belonging to a partner moves its amounts to that partner,
        even when the lines are in a locked, snapshotted period.
        """
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')

        self.env.company.fiscalyear_lock_date = '2016-12-31'
        self._run_snapshot_crons()
        snapshots_before = self._get_partner_ledger_snapshots()
        self.assertEqual(len(snapshots_before), 2)

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                          Balance
            [   0,                            9],
            [
                ('Partner Ledger',            650.0),
                ('partner_a',                1100.0),
                ('partner_b',                -300.0),
                ('Unknown Partner',          -150.0),
                ('Total Partner Ledger',      650.0),
            ],
            options,
        )

        # Reconcile the 2016 partner-less receivable line with partner_a's 2016 receivable line
        no_partner_line = self.move_2016_b.line_ids.filtered(lambda line: line.name == '2016_b_1')
        partner_a_line = self.move_2016_a.line_ids.filtered(lambda line: line.name == '2016_a_1')
        (no_partner_line + partner_a_line).reconcile()

        # 100.0 of that unallocated credit now belongs to partner_a: it pays their 2016 receivable, lowering their
        # balance to the 1000.0 of 2017, and only the unreconciled remainder stays under 'Unknown Partner'. The
        # total is unchanged, the amount having merely moved between the two groups.
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                          Balance
            [   0,                            9],
            [
                ('Partner Ledger',            650.0),
                ('partner_a',                1000.0),
                ('partner_b',                -300.0),
                ('Unknown Partner',           -50.0),
                ('Total Partner Ledger',      650.0),
            ],
            options,
        )

        # The snapshots themselves are still there, unchanged
        self.assertEqual(self._get_partner_ledger_snapshots(), snapshots_before)

    def test_partner_ledger_snapshot_partner_merge_garbage_collection(self):
        """ Merging partners rewrites the partner of the move lines without lock date protection; all snapshots
        grouped by partner must then be regenerated.
        """
        self.env.company.fiscalyear_lock_date = '2016-12-31'
        self._run_snapshot_crons()
        self.assertEqual(len(self._get_partner_ledger_snapshots()), 2)

        dummy_partner_1, dummy_partner_2 = self.env['res.partner'].create([{'name': 'dummy 1'}, {'name': 'dummy 2'}])
        self.env['base.partner.merge.automatic.wizard']._merge((dummy_partner_1 + dummy_partner_2).ids, dummy_partner_1)

        # Only the snapshots grouped on the partners are garbage collected; the ones of the line totals are kept
        remaining_snapshots = self._get_partner_ledger_snapshots()
        self.assertEqual(remaining_snapshots.mapped('groupby'), [False])
