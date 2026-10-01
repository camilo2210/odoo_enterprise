from datetime import date
from .common import TestAccountReportsCommon

from odoo import fields
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestGeneralLedgerSnapshots(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        for company in cls.env.companies:
            assert not company.hard_lock_date
            company.fiscalyear_lock_date = None
            company.tax_lock_date = None

        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company_data['company'].ids))

        # Only the General Ledger should generate snapshots in these tests
        cls.env['account.report'].search([]).enable_snapshots = False
        cls.report = cls.env.ref('account_reports.general_ledger_report')
        cls.report.enable_snapshots = True

        cls.snapshot_creation_cron = cls.env.ref('account_reports.ir_cron_create_snapshots')
        cls.snapshot_garbage_collection_cron = cls.env.ref('account_reports.ir_cron_garbage_collect_snapshots')

        cls.account_bank = cls.company_data['default_account_assets']
        cls.account_revenue = cls.company_data['default_account_revenue']

        # Entries in 2016 (initial balance)
        cls.move_2016 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-06-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 100.0, 'credit': 0.0, 'name': '2016_bank', 'account_id': cls.account_bank.id}),
                (0, 0, {'debit': 0.0, 'credit': 100.0, 'name': '2016_revenue', 'account_id': cls.account_revenue.id}),
            ],
        })

        # Entries in 2017 (period data)
        cls.move_2017 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2017-06-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 50.0, 'credit': 0.0, 'name': '2017_bank', 'account_id': cls.account_bank.id}),
                (0, 0, {'debit': 0.0, 'credit': 50.0, 'name': '2017_revenue', 'account_id': cls.account_revenue.id}),
            ],
        })

        (cls.move_2016 + cls.move_2017).action_post()

        cls._cleanup_cron_triggers()

    @classmethod
    def _cleanup_cron_triggers(cls):
        cls.env['ir.cron.trigger'].search([('cron_id', 'in', (cls.snapshot_garbage_collection_cron + cls.snapshot_creation_cron).ids)]).unlink()

    def _run_snapshot_crons(self):
        self.env['account.report.snapshot'].sudo()._cron_garbage_collect_snapshots()
        while creation_trigger := self.env['ir.cron.trigger'].search([('cron_id', '=', self.snapshot_creation_cron.id)], limit=1):
            creation_trigger.unlink()
            self.env['account.report.snapshot'].sudo()._cron_create_snapshots()

    def _get_general_ledger_snapshots(self):
        return self.env['account.report.snapshot'].sudo().search([('report_id', '=', self.report.id)]).sorted(lambda snapshot: snapshot.groupby or '')

    def test_general_ledger_snapshot_lifecycle(self):
        """
        The General Ledger's initial balances must be snapshotted when a lock date is set,
        and give the exact same report content as a full computation.
        """
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')

        # Fetch without snapshots
        self.assertFalse(self._get_general_ledger_snapshots())
        lines_without_snapshot = self.report._get_lines(options)
        values_without_snapshot = [(l.name, [c.no_format for c in l.columns]) for l in lines_without_snapshot]

        # Set lock date & create snapshots
        self.env.company.fiscalyear_lock_date = '2016-12-31'
        self._run_snapshot_crons()

        snapshots = self._get_general_ledger_snapshots()
        self.assertTrue(snapshots)

        self.assertEqual(
            [(snapshot.groupby, snapshot.date, snapshot.engine_func) for snapshot in snapshots],
            [
                (False, date(2016, 12, 31), '_report_engine_gl_initial_balance'),
                ('account_id', date(2016, 12, 31), '_report_engine_gl_initial_balance'),
            ],
        )

        # Fetch with snapshots
        lines_with_snapshot = self.report._get_lines(options)
        values_with_snapshot = [(l.name, [c.no_format for c in l.columns]) for l in lines_with_snapshot]
        self.assertEqual(values_without_snapshot, values_with_snapshot)

        # Corrupt the snapshot to prove it skips recomputation
        for snapshot in snapshots.filtered(lambda s: not s.groupby):
            corrupted_result = {}
            for expr_key, formula_result in snapshot.result.items():
                if isinstance(formula_result, list):
                    corrupted_list = []
                    for grouping_key, row_dict in formula_result:
                        corrupted_row = dict(row_dict)
                        if 'balance' in corrupted_row:
                            corrupted_row['balance'] = corrupted_row.get('balance', 0) + 999.0
                        if 'init_balance' in corrupted_row:
                            corrupted_row['init_balance'] = corrupted_row.get('init_balance', 0) + 999.0
                        corrupted_list.append((grouping_key, corrupted_row))
                    corrupted_result[expr_key] = corrupted_list
                else:
                    corrupted_row = dict(formula_result)
                    if 'balance' in corrupted_row:
                        corrupted_row['balance'] = corrupted_row.get('balance', 0) + 999.0
                    if 'init_balance' in corrupted_row:
                        corrupted_row['init_balance'] = corrupted_row.get('init_balance', 0) + 999.0
                    corrupted_result[expr_key] = corrupted_row
            snapshot.result = corrupted_result

        lines_corrupted = self.report._get_lines(options)
        corrupted_values = [(l.name, [c.no_format for c in l.columns]) for l in lines_corrupted]

        expected_corrupted_values = []
        for name, cols in values_without_snapshot:
            new_cols = list(cols)
            if name == 'Total General Ledger':
                new_cols[-1] = (new_cols[-1] or 0.0) + 999.0
            expected_corrupted_values.append((name, new_cols))

        self.assertEqual(
            expected_corrupted_values,
            corrupted_values,
        )

        # Garbage collection
        self.env.company.fiscalyear_lock_date = '2015-12-31'
        self._run_snapshot_crons()

        snapshots_after_gc = self._get_general_ledger_snapshots()
        self.assertEqual(
            [(snapshot.groupby, snapshot.date, snapshot.engine_func) for snapshot in snapshots_after_gc],
            [
                (False, date(2015, 12, 31), '_report_engine_gl_initial_balance'),
                ('account_id', date(2015, 12, 31), '_report_engine_gl_initial_balance'),
            ],
        )

        lines_restored = self.report._get_lines(options)
        values_restored = [(l.name, [c.no_format for c in l.columns]) for l in lines_restored]
        self.assertEqual(values_without_snapshot, values_restored)

    def test_general_ledger_snapshot_open_period_merge(self):
        """
        When a fiscal year lock date is set, the snapshot generated must align with that
        lock date. Subsequent reports covering open periods must inherit their historical
        initial balances directly from this cached snapshot rather than recomputing.
        """
        # Create a transaction in 2025 (Locked Year) and 2026 (Open Year)
        move_2025 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2025-06-01'),
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 500.0, 'credit': 0.0, 'name': '2025_bank', 'account_id': self.account_bank.id}),
                (0, 0, {'debit': 0.0, 'credit': 500.0, 'name': '2025_revenue', 'account_id': self.account_revenue.id}),
            ],
        })
        move_2026 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2026-06-01'),
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 100.0, 'credit': 0.0, 'name': '2026_bank', 'account_id': self.account_bank.id}),
                (0, 0, {'debit': 0.0, 'credit': 100.0, 'name': '2026_revenue', 'account_id': self.account_revenue.id}),
            ],
        })
        (move_2025 + move_2026).action_post()

        # Lock the end of 2025 and trigger the cron
        self.env.company.fiscalyear_lock_date = '2025-12-31'
        self._run_snapshot_crons()

        snapshots = self._get_general_ledger_snapshots()

        # The latest snapshot must be dated exactly at the lock date (2025-12-31).
        self.assertTrue(snapshots)
        latest_snapshot_date = max(snapshots.mapped('date'))
        self.assertEqual(latest_snapshot_date, date(2025, 12, 31))

        # Generate the report for mid-2026
        options_2026 = self._generate_options(self.report, '2026-07-01', '2026-07-31')
        lines_uncorrupted = self.report._get_lines(options_2026)
        values_uncorrupted = [(l.name, [c.no_format for c in l.columns]) for l in lines_uncorrupted]

        # Corrupt the 2025 snapshot to prove the locked values are pulled from cache, not recomputed
        snapshot_2025 = snapshots.filtered(lambda s: s.date == date(2025, 12, 31))
        for snapshot in snapshot_2025:
            corrupted_result = {}
            for expr_key, formula_result in snapshot.result.items():
                if isinstance(formula_result, list):
                    corrupted_list = []
                    for grouping_key, row_dict in formula_result:
                        corrupted_row = dict(row_dict)
                        if 'balance' in corrupted_row:
                            corrupted_row['balance'] = corrupted_row.get('balance', 0) + 999.0
                        if 'init_balance' in corrupted_row:
                            corrupted_row['init_balance'] = corrupted_row.get('init_balance', 0) + 999.0
                        corrupted_list.append((grouping_key, corrupted_row))
                    corrupted_result[expr_key] = corrupted_list
                else:
                    corrupted_row = dict(formula_result)
                    if 'balance' in corrupted_row:
                        corrupted_row['balance'] = corrupted_row.get('balance', 0) + 999.0
                    if 'init_balance' in corrupted_row:
                        corrupted_row['init_balance'] = corrupted_row.get('init_balance', 0) + 999.0
                    corrupted_result[expr_key] = corrupted_row
            snapshot.result = corrupted_result

        # Generating the mid-2026 report should inherit the corrupted 2025 data
        lines_corrupted = self.report._get_lines(options_2026)
        values_corrupted = [(l.name, [c.no_format for c in l.columns]) for l in lines_corrupted]
        self.assertNotEqual(values_uncorrupted, values_corrupted)
