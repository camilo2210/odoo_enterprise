from datetime import date, datetime
from unittest.mock import patch

from .common import TestAccountReportsCommon

from odoo import Command, fields
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestSnapshots(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    class snapshot_test_patch:
        def __init__(self, test_class, report, report_query_count, partition_count):
            self.test_class = test_class
            self.report = report
            self.report_query_counts_left = report_query_count
            self.partition_count = partition_count

            self.orig_get_report_query = report._get_report_query
            self.orig_merge_result_partitions = report.env['account.report.snapshot']._merge_result_partitions

            self.report_query_patch = patch.object(report.__class__, '_get_report_query', self._mocked_get_report_query)
            self.snapshot_merge_patch = patch.object(report.env['account.report.snapshot'].__class__, '_merge_result_partitions', self._mocked_merge_result_partitions)

        def __enter__(self):
            self.report_query_patch.__enter__()
            self.snapshot_merge_patch.__enter__()
            return self

        def __exit__(self, exception_type, exception_val, exception_tb):
            self.report_query_patch.__exit__(exception_type, exception_val, exception_tb)
            self.snapshot_merge_patch.__exit__(exception_type, exception_val, exception_tb)

            self.test_class.assertFalse(self.report_query_counts_left, "Not enough report queries run !")

        def _mocked_get_report_query(self, options, date_scope, domain=None):
            self.test_class.assertTrue(self.report_query_counts_left > 0, "Too many report queries run !")
            self.report_query_counts_left -= 1
            return self.orig_get_report_query(options, date_scope, domain=domain)

        def _mocked_merge_result_partitions(self, result_partitions, result_aggregators):
            self.test_class.assertEqual(len(result_partitions), self.partition_count)
            return self.orig_merge_result_partitions(result_partitions, result_aggregators)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['account.report'].search([]).enable_snapshots = False  # To make sure calling the cron in the tess does not compute useless things
        cls.company_data['company'].account_fiscal_country_id = cls.fake_country

        for company in cls.env.companies:
            assert not company.hard_lock_date  # Make sure we crash if the common test setup changes in the future
            company.fiscalyear_lock_date = None
            company.tax_lock_date = None

        cls._cleanup_snapshot_cron_triggers()

    def _simulate_crons_after_lock_date_change(self, expected_snapshot_nber, stop_when_reached=False, only_creation=False):
        if not only_creation:
            self.assertEqual(0, self.env['ir.cron.trigger'].search_count([('cron_id', '=', self.snapshot_creation_cron.id)]))

            gc_triggers = self.env['ir.cron.trigger'].search([('cron_id', '=', self.snapshot_garbage_collection_cron.id)])
            self.assertTrue(gc_triggers)
            gc_triggers.unlink()

            self.env['account.report.snapshot'].sudo()._cron_garbage_collect_snapshots()

        created_snapshots_count = 0
        while creation_trigger := self.env['ir.cron.trigger'].search([('cron_id', '=', self.snapshot_creation_cron.id)], limit=1):
            creation_trigger.unlink()
            created = self.env['account.report.snapshot'].sudo()._cron_create_snapshots()
            if created:
                created_snapshots_count += 1
                if stop_when_reached and created_snapshots_count == expected_snapshot_nber:
                    break

        self.assertEqual(created_snapshots_count, expected_snapshot_nber)

    def test_snapshots_basic(self):
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.env.company.ids))

        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2020-01-01'),
            self._prepare_test_account_move_line(2.0, account_code='200000', date='2020-01-01'),
            self._prepare_test_account_move_line(11.0, account_code='110000', date='2020-03-01'),
            self._prepare_test_account_move_line(12.0, account_code='120000', date='2021-01-01'),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1'), groupby='account_id', foldability='foldable'),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('2'), groupby='account_id', foldability='foldable'),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        options = self._generate_options(report, '2020-12-31', '2020-12-31')

        # No snapshot yet
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',          12.0),
                    ('test_line_2',           2.0),
                ],
                options,
            )

        self.env.company.fiscalyear_lock_date = '2020-12-31'

        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1)

        # A snapshot exists at this date ; the engine shouldn't be called at all
        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           12.0),
                    ('test_line_2',            2.0),
                ],
                options,
            )

        # When computing groupbys, snapshots aren't called (yet) => subject to change in the future, with the rollups
        # One call to the engine is made for the groupby for each line to unfold (2 in total), and the snapshot is used for the ungrouped lines
        unfold_all_options = {**options, 'unfold_all': True}
        with self.snapshot_test_patch(self, report, 2, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(unfold_all_options),
                [   0,                          1],
                [
                    ('test_line_1',           12.0),
                    ('100000 100000',          1.0),
                    ('110000 110000',         11.0),
                    ('Total test_line_1',     12.0),
                    ('test_line_2',            2.0),
                    ('200000 200000',          2.0),
                    ('Total test_line_2',      2.0),
                ],
                unfold_all_options,
            )

        # A snapshot exists at an earlier date, and needs to be combined with the data from the period between its date and the required date
        options_after_lock_date = self._generate_options(report, '2021-01-01', '2021-01-01')
        with self.snapshot_test_patch(self, report, 1, 2):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_after_lock_date),
                [   0,                          1],
                [
                    ('test_line_1',          24.0),
                    ('test_line_2',           2.0),
                ],
                options_after_lock_date,
            )

    def test_snapshots_to_beginning_of_fiscalyear(self):
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.env.company.ids))

        # The 2021 move is never part of the result: it only ensures the evaluated bound doesn't reach the options' date_to.
        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2019-06-01'),
            self._prepare_test_account_move_line(10.0, account_code='100000', date='2020-06-01'),
            self._prepare_test_account_move_line(100.0, account_code='100000', date='2021-06-01'),
        ])

        report = self._create_report(
            [self._prepare_test_report_line(self._prepare_test_expression_account_codes('1', date_scope='to_beginning_of_fiscalyear'))],
            filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id,
        )

        self._cleanup_snapshot_cron_triggers()

        # The 2020 fiscal year starts on 2020-01-01: only the 2019 move is evaluated.
        options_2020 = self._generate_options(report, '2020-12-31', '2020-12-31')
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_2020),
                [   0,                          1],
                [
                    ('test_line_1',           1.0),
                ],
                options_2020,
            )

        self.env.company.fiscalyear_lock_date = '2020-12-31'

        # snapshot the earliest fiscal year
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        # ...then fills the gap up to the lock date
        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True)

        self.assertRecordValues(
            self.env['account.report.snapshot'].search([('report_id', '=', report.id)], order='date'),
            [
                {'date': date(2019, 12, 31), 'date_scope': 'to_beginning_of_fiscalyear'},
                {'date': date(2020, 12, 31), 'date_scope': 'to_beginning_of_fiscalyear'},
            ],
        )

        # Evaluating the 2020 fiscal year, whose eve-of-fiscal-year bound is 2019-12-31: the snapshot
        # covers it exactly, so it's used directly and the engine isn't called.
        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_2020),
                [   0,                          1],
                [
                    ('test_line_1',           1.0),
                ],
                options_2020,
            )

        # One fiscal year later, the bound to evaluate becomes the lock date itself: the snapshot covers it
        # exactly, and the engine isn't called.
        options_2021 = self._generate_options(report, '2021-12-31', '2021-12-31')
        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_2021),
                [   0,                          1],
                [
                    ('test_line_1',          11.0),
                ],
                options_2021,
            )

    def test_snapshots_multicompany_synced_no_branch(self):
        new_company = self._create_company(name='other test company')
        new_company.account_fiscal_country_id = self.fake_country
        companies = self.env.company + new_company

        self.env = self.env(context=dict(self.env.context, allowed_company_ids=companies.ids))

        # garbage_account needs to be shared so that the auto-created balancing line can be added by _create_test_account_moves
        self.garbage_account.with_context(allowed_company_ids=[new_company.id, self.env.company.id]).write({
            'code': 'turlututu',
            'company_ids': [Command.link(new_company.id)],
        })
        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2020-12-31', company_id=companies[0].id),
            self._prepare_test_account_move_line(2.0, account_code='200000', date='2020-12-31', company_id=companies[0].id),

            self._prepare_test_account_move_line(1.1, account_code='100000', date='2020-12-31', company_id=companies[1].id),
            self._prepare_test_account_move_line(2.1, account_code='200000', date='2020-12-31', company_id=companies[1].id),

            self._prepare_test_account_move_line(10.0, account_code='100000', date='2022-01-01', company_id=companies[0].id),

            self._prepare_test_account_move_line(10.1, account_code='100000', date='2022-01-01', company_id=companies[1].id),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('2')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        # No snapshot yet
        options = self._generate_options(report, '2021-12-31', '2021-12-31')
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           2.1),
                    ('test_line_2',           4.1),
                ],
                options,
            )

        # Create snapshots
        companies.fiscalyear_lock_date = '2021-12-31'

        # Snapshots of company 0
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        # Snapshots of company 1
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True)

        # Snapshots match the date exactly, no query should be executed, and both snapshots should be combined to build the result
        with self.snapshot_test_patch(self, report, 0, 2):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           2.1),
                    ('test_line_2',           4.1),
                ],
                options,
            )

        options_after_lock_date = self._generate_options(report, '2022-12-31', '2022-12-31')
        # 3 partitions should be combined: 2 snapshots + 1 engine call for what comes after the snapshots
        with self.snapshot_test_patch(self, report, 1, 3):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_after_lock_date),
                [   0,                          1],
                [
                    ('test_line_1',          22.2),
                    ('test_line_2',           4.1),
                ],
                options_after_lock_date,
            )

    def test_snapshots_multicompany_synced_branches(self):
        main_company = self.env.company
        branch = self.env['res.company'].create({'name': 'branch', 'parent_id': main_company.id, 'account_fiscal_country_id': self.fake_country.id})
        sub_branch = self.env['res.company'].create({'name': 'branch branch', 'parent_id': branch.id, 'account_fiscal_country_id': self.fake_country.id})

        self.env = self.env(context=dict(self.env.context, allowed_company_ids=(self.env.company + branch + sub_branch).ids))

        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2020-12-31', company_id=main_company.id),
            self._prepare_test_account_move_line(2.0, account_code='200000', date='2020-12-31', company_id=main_company.id),

            self._prepare_test_account_move_line(1.1, account_code='100000', date='2020-12-31', company_id=branch.id),
            self._prepare_test_account_move_line(2.1, account_code='200000', date='2020-12-31', company_id=branch.id),

            self._prepare_test_account_move_line(1.2, account_code='100000', date='2020-12-31', company_id=sub_branch.id),
            self._prepare_test_account_move_line(2.2, account_code='200000', date='2020-12-31', company_id=sub_branch.id),

            self._prepare_test_account_move_line(10.0, account_code='100000', date='2022-01-01', company_id=main_company.id),
            self._prepare_test_account_move_line(10.1, account_code='100000', date='2022-01-01', company_id=branch.id),
            self._prepare_test_account_move_line(10.2, account_code='100000', date='2022-01-01', company_id=sub_branch.id),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('2')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        # No snapshot yet
        options = self._generate_options(report, '2021-12-31', '2021-12-31')
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           3.3),
                    ('test_line_2',           6.3),
                ],
                options,
            )

        # Setting the lock date on the main company should snapshot all the branches
        main_company.fiscalyear_lock_date = '2021-12-31'

        # Snapshots of main company
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        # Snapshots of branch
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        # Snapshots of sub branch
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True)

        # The engine shouldn't be called, and the 3 snapshots created for the companies should be combined
        with self.snapshot_test_patch(self, report, 0, 3):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           3.3),
                    ('test_line_2',           6.3),
                ],
                options,
            )

        options_after_lock_date = self._generate_options(report, '2022-12-31', '2022-12-31')
        # The engine should be called one time (for all branches at once), and its results combined with the 3 existing snapshots
        with self.snapshot_test_patch(self, report, 1, 4):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_after_lock_date),
                [   0,                          1],
                [
                    ('test_line_1',          33.6),
                    ('test_line_2',           6.3),
                ],
                options_after_lock_date,
            )

    def test_snapshots_multicompany_non_synced_no_branch(self):
        new_companies = self.env['res.company']
        for i in range(2):
            new_company = self._create_company(name=f'other test company {i}')
            new_company.account_fiscal_country_id = self.fake_country
            new_companies += new_company

            # garbage_account needs to be shared so that the auto-created balancing line can be added by _create_test_account_moves
            self.garbage_account.with_context(allowed_company_ids=[new_company.id, self.env.company.id]).write({
                'code': 'turlututu',
                'company_ids': [Command.link(new_company.id)],
            })

        companies = self.env.company + new_companies
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=companies.ids))

        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2020-12-31', company_id=companies[0].id),
            self._prepare_test_account_move_line(2.0, account_code='200000', date='2020-12-31', company_id=companies[0].id),
            self._prepare_test_account_move_line(21.0, account_code='210000', date='2021-07-01', company_id=companies[0].id),

            self._prepare_test_account_move_line(1.1, account_code='100000', date='2020-12-31', company_id=companies[1].id),
            self._prepare_test_account_move_line(2.1, account_code='200000', date='2020-12-31', company_id=companies[1].id),
            self._prepare_test_account_move_line(21.1, account_code='210000', date='2021-07-01', company_id=companies[1].id),

            self._prepare_test_account_move_line(1.3, account_code='100000', date='2020-12-31', company_id=companies[2].id),
            self._prepare_test_account_move_line(2.3, account_code='200000', date='2020-12-31', company_id=companies[2].id),
            self._prepare_test_account_move_line(21.3, account_code='210000', date='2021-07-01', company_id=companies[2].id),

            self._prepare_test_account_move_line(10.0, account_code='100000', date='2022-01-01', company_id=companies[0].id),

            self._prepare_test_account_move_line(10.1, account_code='100000', date='2022-01-01', company_id=companies[1].id),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('2')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        # No snapshot yet
        options = self._generate_options(report, '2021-12-31', '2021-12-31')
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           3.4),
                    ('test_line_2',          69.8),
                ],
                options,
            )

        # Create snapshots
        companies[0].fiscalyear_lock_date = '2021-12-31'
        companies[1].fiscalyear_lock_date = '2021-06-30'
        # No lock date on companies[2], on purpose

        # Snapshots of company 0
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        # Snapshots of company 1
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True)

        # Snapshots match the date exactly for company 0, but not company 1: 1 call to the engine for company 1 + 2 snapshots to combine with the result
        with self.snapshot_test_patch(self, report, 1, 3):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           3.4),
                    ('test_line_2',          69.8),
                ],
                options,
            )

        options_after_lock_date = self._generate_options(report, '2022-12-31', '2022-12-31')
        # 3 partitions should be combined: 2 snapshots + 1 engine call for what comes after the snapshots
        with self.snapshot_test_patch(self, report, 1, 3):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_after_lock_date),
                [   0,                          1],
                [
                    ('test_line_1',          23.5),
                    ('test_line_2',          69.8),
                ],
                options_after_lock_date,
            )

    def test_snapshots_multicompany_non_synced_branches(self):
        main_company = self.env.company
        branch = self.env['res.company'].create({'name': 'branch', 'parent_id': main_company.id, 'account_fiscal_country_id': self.fake_country.id})
        sub_branch = self.env['res.company'].create({'name': 'branch branch', 'parent_id': branch.id, 'account_fiscal_country_id': self.fake_country.id})

        self.env = self.env(context=dict(self.env.context, allowed_company_ids=(self.env.company + branch + sub_branch).ids))

        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2020-12-31', company_id=main_company.id),
            self._prepare_test_account_move_line(2.0, account_code='200000', date='2020-12-31', company_id=main_company.id),
            self._prepare_test_account_move_line(21.0, account_code='210000', date='2021-07-01', company_id=main_company.id),

            self._prepare_test_account_move_line(1.1, account_code='100000', date='2020-12-31', company_id=branch.id),
            self._prepare_test_account_move_line(2.1, account_code='200000', date='2020-12-31', company_id=branch.id),
            self._prepare_test_account_move_line(21.1, account_code='210000', date='2021-07-01', company_id=branch.id),

            self._prepare_test_account_move_line(1.2, account_code='100000', date='2020-12-31', company_id=sub_branch.id),
            self._prepare_test_account_move_line(2.2, account_code='200000', date='2020-12-31', company_id=sub_branch.id),
            self._prepare_test_account_move_line(21.2, account_code='210000', date='2021-07-01', company_id=sub_branch.id),

            self._prepare_test_account_move_line(10.0, account_code='100000', date='2022-01-01', company_id=main_company.id),
            self._prepare_test_account_move_line(10.1, account_code='100000', date='2022-01-01', company_id=branch.id),
            self._prepare_test_account_move_line(10.2, account_code='100000', date='2022-01-01', company_id=sub_branch.id),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('2')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        # No snapshot yet
        options = self._generate_options(report, '2021-12-31', '2021-12-31')
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           3.3),
                    ('test_line_2',          69.6),
                ],
                options,
            )

        # Set non-identical lock dates (none on the parent company)
        branch.fiscalyear_lock_date = '2021-12-31'
        sub_branch.fiscalyear_lock_date = '2021-06-30'

        # Snapshots of branch
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        # Snapshots of sub_branch
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, only_creation=True, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 1, 2):
            self._simulate_crons_after_lock_date_change(1, only_creation=True)

        # The engine should be called for main company and the non-snapshot part of sub_branch ; the result should be combined with the existing 2 snapshots
        with self.snapshot_test_patch(self, report, 1, 3):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           3.3),
                    ('test_line_2',          69.6),
                ],
                options,
            )

        options_after_lock_date = self._generate_options(report, '2022-12-31', '2022-12-31')
        # The engine should be called one time (for all branches at once), and its results combined with the 2 existing snapshots
        with self.snapshot_test_patch(self, report, 1, 3):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_after_lock_date),
                [   0,                          1],
                [
                    ('test_line_1',          33.6),
                    ('test_line_2',          69.6),
                ],
                options_after_lock_date,
            )

    def test_multiple_snapshots(self):
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.env.company.ids))

        self._create_test_account_moves([
            self._prepare_test_account_move_line(3.0, account_code='300000', date='2010-01-01'),

            self._prepare_test_account_move_line(1.0, account_code='100000', date='2020-01-01'),
            self._prepare_test_account_move_line(2.0, account_code='200000', date='2020-01-01'),
            self._prepare_test_account_move_line(11.0, account_code='100000', date='2020-03-01'),

            self._prepare_test_account_move_line(12.0, account_code='100000', date='2021-01-01'),

            self._prepare_test_account_move_line(12.1, account_code='100000', date='2022-01-01'),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('2')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        # No snapshot
        options = self._generate_options(report, '2021-12-31', '2021-12-31')
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           24.0),
                    ('test_line_2',            2.0),
                ],
                options,
            )

        self.env.company.fiscalyear_lock_date = '2021-12-31'

        # 5 snapshots will be generated
        # The first snapshot is created without merging it with anything that came before
        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        # Each following snapshot shout merge its computed result with the previous snapshot
        with self.snapshot_test_patch(self, report, 5, 2):
            self._simulate_crons_after_lock_date_change(5, only_creation=True)

        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           24.0),
                    ('test_line_2',            2.0),
                ],
                options,
            )

        # Doing a comparison with only periods covered by the snapshots should not call any report queries
        comparison_options_1 = self._update_comparison_filter(options, report, 'previous_period', 4, date_to=fields.Date.from_string('2021-12-31'))
        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(comparison_options_1),
                #                             2021    2020    2019    2018    2017
                [   0,                          1,      2,      3,      4,      5],
                [
                    ('test_line_1',          24.0,   12.0,    0.0,    0.0,    0.0),
                    ('test_line_2',           2.0,    2.0,    0.0,    0.0,    0.0),
                ],
                comparison_options_1,
            )

        # When comparing with periods not covered by the snapshots, those periods should each call a report query
        comparison_options_2 = self._update_comparison_filter(options, report, 'previous_period', 6, date_to=fields.Date.from_string('2021-12-31'))
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(comparison_options_2),
                #                             2021    2020    2019    2018    2017    2016    2015
                [   0,                          1,      2,      3,      4,      5,      6,      7],
                [
                    ('test_line_1',          24.0,   12.0,    0.0,    0.0,    0.0,    0.0,    0.0),
                    ('test_line_2',           2.0,    2.0,    0.0,    0.0,    0.0,    0.0,    0.0),
                ],
                comparison_options_2,
            )

    def test_snapshots_account_codes_engine_balance_characters(self):
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.env.company.ids))

        self._create_test_account_moves([
            self._prepare_test_account_move_line(-1.0, account_code='100000', date='2019-12-31'),
            self._prepare_test_account_move_line(-11.0, account_code='100000', date='2019-12-31'),
            self._prepare_test_account_move_line(-30.0, account_code='110000', date='2019-12-31'),


            self._prepare_test_account_move_line(13.0, account_code='100000', date='2021-01-01'),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1D')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1C')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('10')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('10D')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('10C')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('11')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('11D')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('11C')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        # Global setup
        options_2020 = self._generate_options(report, '2020-12-31', '2020-12-31')
        options_2021 = self._generate_options(report, '2021-12-31', '2021-12-31')

        lines_2020 = [
            ('test_line_1',          -42.0),
            ('test_line_2',            0.0),
            ('test_line_3',          -42.0),
            ('test_line_4',          -12.0),
            ('test_line_5',            0.0),
            ('test_line_6',          -12.0),
            ('test_line_7',          -30.0),
            ('test_line_8',            0.0),
            ('test_line_9',          -30.0),
        ]

        lines_2021 = [
            ('test_line_1',          -29.0),
            ('test_line_2',            1.0),
            ('test_line_3',          -30.0),
            ('test_line_4',            1.0),
            ('test_line_5',            1.0),
            ('test_line_6',            0.0),
            ('test_line_7',          -30.0),
            ('test_line_8',            0.0),
            ('test_line_9',          -30.0),
        ]

        # No snapshot
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_2020),
                [   0,                          1],
                lines_2020,
                options_2020,
            )

        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_2021),
                [   0,                          1],
                lines_2021,
                options_2021,
            )

        # Create snapshots
        self.env.company.fiscalyear_lock_date = '2021-12-31'

        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        with self.snapshot_test_patch(self, report, 2, 2):
            self._simulate_crons_after_lock_date_change(2, only_creation=True)

        # With snapshots
        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_2020),
                [0, 1],
                lines_2020,
                options_2020,
            )

        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_2021),
                [0, 1],
                lines_2021,
                options_2021,
            )

    def test_snapshots_domain_engine(self):
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.env.company.ids))

        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2020-01-01'),
            self._prepare_test_account_move_line(2.0, account_code='200000', date='2020-01-01'),
            self._prepare_test_account_move_line(11.0, account_code='110000', date='2020-03-01'),
            self._prepare_test_account_move_line(12.0, account_code='120000', date='2021-01-01'),
        ])

        domain_1 = [('account_id.code', '=like', '1%')]
        domain_2 = [('account_id.code', '=like', '2%')]

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_domain(domain_1, 'sum')),
            self._prepare_test_report_line(self._prepare_test_expression_domain(domain_1, '-sum')),
            self._prepare_test_report_line(self._prepare_test_expression_domain(domain_2, 'sum')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        options = self._generate_options(report, '2020-12-31', '2020-12-31')

        # No snapshot yet
        with self.snapshot_test_patch(self, report, 1, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           12.0),
                    ('test_line_2',          -12.0),
                    ('test_line_3',            2.0),
                ],
                options,
            )

        # Locking the period triggers the creation of a snapshot at the lock date.
        self.env.company.fiscalyear_lock_date = '2020-12-31'

        with self.snapshot_test_patch(self, report, 1, 1):
            self._simulate_crons_after_lock_date_change(1)

        # A snapshot now fully covers the period: the engine shouldn't be called at all.
        with self.snapshot_test_patch(self, report, 0, 1):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options),
                [   0,                          1],
                [
                    ('test_line_1',           12.0),
                    ('test_line_2',          -12.0),
                    ('test_line_3',            2.0),
                ],
                options,
            )

        # For a later date, the snapshot is combined with a single engine call covering only the uncovered
        # period (the 2021 move). This merges 2 partitions (snapshot + gap) on both the 'sum' and '-sum' keys.
        options_after_lock_date = self._generate_options(report, '2021-01-01', '2021-01-01')
        with self.snapshot_test_patch(self, report, 1, 2):
            self.assertLinesValues(
                # pylint: disable=bad-whitespace
                report._get_lines(options_after_lock_date),
                [   0,                          1],
                [
                    ('test_line_1',           24.0),
                    ('test_line_2',          -24.0),
                    ('test_line_3',            2.0),
                ],
                options_after_lock_date,
            )

    def test_lock_date_impact(self):
        generic_tax_report = self.env.ref('account.generic_tax_report')

        non_tax_report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        tax_report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id, root_report_id=generic_tax_report.id)

        for lock_date_field, lock_date in [('hard_lock_date', '2020-01-01'), ('fiscalyear_lock_date', '2021-01-01'), ('tax_lock_date', '2022-01-01')]:
            self._cleanup_snapshot_cron_triggers()
            self.env.company.write({lock_date_field: lock_date})
            self._simulate_crons_after_lock_date_change(1)

        tax_report_snapshots = self.env['account.report.snapshot'].search([('report_id', '=', tax_report.id)])
        self.assertEqual(tax_report_snapshots.mapped('date'), [date(2022, 1, 1)])

        non_tax_report_snapshots = self.env['account.report.snapshot'].search([('report_id', '=', non_tax_report.id)])
        self.assertEqual(non_tax_report_snapshots.mapped('date'), [date(2020, 1, 1), date(2021, 1, 1)])

    def test_lock_date_snapshot_garbage_collection(self):
        self._create_test_account_moves([
            self._prepare_test_account_move_line(1.0, account_code='100000', date='2010-01-01'),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()

        # Create snapshots
        self.env.company.fiscalyear_lock_date = '2021-12-31'
        self._simulate_crons_after_lock_date_change(6)

        self.assertEqual(
            self.env['account.report.snapshot'].search([('report_id', '=', report.id)]).mapped('date'),
            [
                date(2016, 12, 31),
                date(2017, 12, 31),
                date(2018, 12, 31),
                date(2019, 12, 31),
                date(2020, 12, 31),
                date(2021, 12, 31),
            ]
        )

        # Chaging the lock date should garbage collect the following snapshots
        self.env.company.fiscalyear_lock_date = '2019-12-31'
        self._simulate_crons_after_lock_date_change(0)

        self.assertEqual(
            self.env['account.report.snapshot'].search([('report_id', '=', report.id)]).mapped('date'),
            [
                date(2016, 12, 31),
                date(2017, 12, 31),
                date(2018, 12, 31),
                date(2019, 12, 31),
            ]
        )

        # Adding a lock date exception should also garbage collect the invalidated snapshots
        lock_date_wizard = self.env['account.change.lock.date'].create({
            'fiscalyear_lock_date': '2018-02-01',
            'exception_applies_to': 'me',
            'exception_duration': 'forever',
            'exception_reason': "Because I'm Batman !",
        })

        lock_date_wizard.change_lock_date()
        self._simulate_crons_after_lock_date_change(0)

        self.assertEqual(
            self.env['account.report.snapshot'].search([('report_id', '=', report.id)]).mapped('date'),
            [
                date(2016, 12, 31),
                date(2017, 12, 31),
            ]
        )

        # Revoking the exception should regenerate the snapshots
        lock_date_wizard.action_revoke_min_fiscalyear_lock_date_exception_for_me()
        self._simulate_crons_after_lock_date_change(2, only_creation=True)

        self.assertEqual(
            self.env['account.report.snapshot'].search([('report_id', '=', report.id)]).mapped('date'),
            [
                date(2016, 12, 31),
                date(2017, 12, 31),
                date(2018, 12, 31),
                date(2019, 12, 31),
            ]
        )

    def test_merge_result_partitions_groupby_lists(self):
        """ Groupby result partitions must merge by grouping key, keeping the list sorted and supporting None keys
        (e.g. the 'Unknown Partner' group).
        """
        aggregators = {'init_balance': sum, 'has_sublines': max}
        partitions = [
            {'batch_key': [
                (3, {'init_balance': 30.0, 'has_sublines': True}),
                (None, {'init_balance': 5.0, 'has_sublines': False}),
            ]},
            {'batch_key': [
                (1, {'init_balance': 10.0, 'has_sublines': False}),
                (3, {'init_balance': 3.0, 'has_sublines': False}),
                (9, {'init_balance': 90.0, 'has_sublines': True}),
            ]},
        ]

        self.assertEqual(
            self.env['account.report.snapshot']._merge_result_partitions(partitions, aggregators),
            {'batch_key': [
                (None, {'init_balance': 5.0, 'has_sublines': False}),
                (1, {'init_balance': 10.0, 'has_sublines': False}),
                (3, {'init_balance': 33.0, 'has_sublines': True}),
                (9, {'init_balance': 90.0, 'has_sublines': True}),
            ]},
        )

    def test_open_ended_lock_exception_snapshot_garbage_collection(self):
        # We need to use mock_datetime_and_now in this test because it uses temporary lock date exceptions, whose business code
        # depends on the create_date of snapshots.
        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
        ], filter_date_range=False, enable_snapshots=True, availability_condition='country', country_id=self.fake_country.id)

        self._cleanup_snapshot_cron_triggers()
        self.env.company.fiscalyear_lock_date = '2021-12-31'
        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 1)):
            self._simulate_crons_after_lock_date_change(1, stop_when_reached=True)

        self.assertTrue(self.env['account.report.snapshot'].search([('report_id', '=', report.id)]))

        # An exception without a lock date unlocks the whole period. Snapshots must be removed
        # and cannot be recreated while it is active.
        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 2)):
            self.env['account.change.lock.date'].create({
                'fiscalyear_lock_date': False,
                'exception_applies_to': 'me',
                'exception_duration': 'forever',
            }).change_lock_date()

        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 3)):
            self._simulate_crons_after_lock_date_change(0)

        self.assertFalse(self.env['account.report.snapshot'].search([('report_id', '=', report.id)]))

        # Do some lock date back and forth to test what is kept or deleted
        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 4)):
            self.env['account.change.lock.date'].create({}).action_revoke_min_fiscalyear_lock_date_exception_for_me()

        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 5)):
            self._simulate_crons_after_lock_date_change(1, only_creation=True)

        created_snapshot_1 = self.env['account.report.snapshot'].search([('report_id', '=', report.id), ('date', '=', '2021-12-31')])
        self.assertEqual(1, len(created_snapshot_1))

        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 6)):
            self.env['account.change.lock.date'].create({'fiscalyear_lock_date': '2022-01-10'}).change_lock_date()

        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 7)):
            self._simulate_crons_after_lock_date_change(1)

        created_snapshot_2 = self.env['account.report.snapshot'].search([('report_id', '=', report.id), ('date', '=', '2022-01-10')])
        self.assertEqual(1, len(created_snapshot_2))

        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 8)):
            self.env['account.change.lock.date'].create({
                'fiscalyear_lock_date': '2022-01-01',
                'exception_applies_to': 'everyone',
                'exception_duration': 'forever',
            }).change_lock_date()

        with self.mock_datetime_and_now(datetime(2026, 1, 1, 10, 9)):
            self._simulate_crons_after_lock_date_change(1)

        # snasphot 2 should have been deleted ; snapshot 1 should still be there
        all_snapshots = self.env['account.report.snapshot'].search([('report_id', '=', report.id)])

        self.assertTrue(created_snapshot_1 in all_snapshots)
        self.assertFalse(created_snapshot_2 in all_snapshots)
        self.assertEqual(len(all_snapshots), 2)
