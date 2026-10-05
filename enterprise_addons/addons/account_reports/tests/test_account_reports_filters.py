# -*- coding: utf-8 -*-
# pylint: disable=C0326
import odoo.tests

from odoo.tests import tagged
from odoo import Command, fields
from .common import TestAccountReportsCommon
from odoo.tools import date_utils
from odoo.tools.misc import formatLang, format_date

from dateutil.relativedelta import relativedelta
from unittest.mock import patch
from freezegun import freeze_time


@tagged('post_install', '-at_install')
class TestAccountReportsFilters(TestAccountReportsCommon, odoo.tests.HttpCase):

    _test_user_groups = None  # FIXME list needed groups

    def _assert_filter_date(self, report, previous_options, expected_date_values):
        """ Initializes and checks the 'date' option computed for the provided report and previous_options
        """
        options = report.get_options(previous_options)
        self.assertDictEqual(options['date'], expected_date_values)

    def _assert_filter_comparison(self, report, previous_options, expected_period_values):
        """ Initializes and checks the 'comparison' option computed for the provided report and previous_options
        """
        options = report.get_options(previous_options)

        self.assertEqual(len(options['comparison']['periods']), len(expected_period_values))

        for i, expected_values in enumerate(expected_period_values):
            self.assertDictEqual(options['comparison']['periods'][i], expected_values)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.single_date_report = cls.env['account.report'].create({
            'name': "Single Date Report",
            'filter_period_comparison': True,
            'filter_date_range': False,
        })

        cls.date_range_report = cls.env['account.report'].create({
            'name': "Date Range Report",
            'filter_period_comparison': True,
        })

        # Test the default account_report reports. Don't choose US variants based on the fiscal country.
        cls.env['account.report'].search([]).variant_report_ids.active = False
        cls.env['account.report'].search([]).filter_journals = True

    @freeze_time('2026-12-31')
    def test_filter_date_non_escalating(self):
        self.env.company.write({
            'fiscalyear_last_month': '6',
            'fiscalyear_last_day': 30,
        })

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}},
            {
                'string': 'Jul 2026 - Jun 2027',
                'period_type': 'year',
                'date_from': '2026-07-01',
                'date_to': '2027-06-30',
            },
        )

        # Simulate another company with normal fiscal year passing the previously generated options
        self.env.company.write({
            'fiscalyear_last_month': '12',
            'fiscalyear_last_day': 31,
        })

        self._assert_filter_date(
            self.date_range_report,
            {
                'date': {
                    'string': 'Jul 2026 - Jun 2027',
                    'period_type': 'year',
                    'date_from': '2026-07-01',
                    'date_to': '2027-06-30',
                }
            },
            {
                'string': '2027',
                'period_type': 'year',
                'date_from': '2027-01-01',
                'date_to': '2027-12-31',
            },
        )

        # Simulate again with the first "company" settings with anualigned fiscal year passing the previously generated options
        self.env.company.write({
            'fiscalyear_last_month': '6',
            'fiscalyear_last_day': 30,
        })

        self._assert_filter_date(
            self.date_range_report,
            {
                'date': {
                    'string': '2027',
                    'period_type': 'year',
                    'date_from': '2027-01-01',
                    'date_to': '2027-12-31',
                }
            },
            {
                'string': 'Jul 2026 - Jun 2027',
                'period_type': 'year',
                'date_from': '2026-07-01',
                'date_to': '2027-06-30',
            },
        )

        # Sanity test, making sure it does not give different things than what was ouputed with the same input.
        self._assert_filter_date(
            self.date_range_report,
            {
                'date': {
                    'string': 'Jul 2026 - Jun 2027',
                    'period_type': 'year',
                    'date_from': '2026-07-01',
                    'date_to': '2027-06-30',
                }
            },
            {
                'string': 'Jul 2026 - Jun 2027',
                'period_type': 'year',
                'date_from': '2026-07-01',
                'date_to': '2027-06-30',
            },
        )

        self.env.company.write({
            'fiscalyear_last_month': '12',
            'fiscalyear_last_day': 31,
        })

        self._assert_filter_date(
            self.date_range_report,
            {
                'date': {
                    'string': '2027',
                    'period_type': 'year',
                    'date_from': '2027-01-01',
                    'date_to': '2027-12-31',
                }
            },
            {
                'string': '2027',
                'period_type': 'year',
                'date_from': '2027-01-01',
                'date_to': '2027-12-31',
            },
        )

    ####################################################
    # DATES RANGE
    ####################################################

    @freeze_time('2017-12-31')
    def test_filter_date_month_range(self):
        ''' Test the filter_date with 'this_month'/'last_month' in 'range' mode.'''
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_month'}},
            {
                'string': 'Dec 2017',
                'period_type': 'month',
                'date_from': '2017-12-01',
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'previous_month'}},
            {
                'string': 'Nov 2017',
                'period_type': 'month',
                'date_from': '2017-11-01',
                'date_to': '2017-11-30',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'next_month'}},
            {
                'string': 'Jan 2018',
                'period_type': 'month',
                'date_from': '2018-01-01',
                'date_to': '2018-01-31',
            },
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_month'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'Nov 2017',
                    'period_type': 'month',
                    'date_from': '2017-11-01',
                    'date_to': '2017-11-30',
                },
                {
                    'string': 'Oct 2017',
                    'period_type': 'month',
                    'date_from': '2017-10-01',
                    'date_to': '2017-10-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_month'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'Dec 2016',
                    'period_type': 'month',
                    'date_from': '2016-12-01',
                    'date_to': '2016-12-31',
                },
                {
                    'string': 'Dec 2015',
                    'period_type': 'month',
                    'date_from': '2015-12-01',
                    'date_to': '2015-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_month'}, 'comparison': {'filter': 'custom', 'date_from': '2016-12-01', 'date_to': '2016-12-31'}},
            [
                {
                    'string': 'Dec 2016',
                    'period_type': 'month',
                    'date_from': '2016-12-01',
                    'date_to': '2016-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_quarter_range(self):
        ''' Test the filter_date with 'this_quarter'/'last_quarter' in 'range' mode.'''
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_quarter'}},
            {
                'string': 'Oct - Dec 2017',
                'period_type': 'quarter',
                'date_from': '2017-10-01',
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'previous_quarter'}},
            {
                'string': 'Jul - Sep 2017',
                'period_type': 'quarter',
                'date_from': '2017-07-01',
                'date_to': '2017-09-30',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'next_quarter'}},
            {
                'string': 'Jan - Mar 2018',
                'period_type': 'quarter',
                'date_from': '2018-01-01',
                'date_to': '2018-03-31',
            },
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_quarter'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'Jul - Sep 2017',
                    'period_type': 'quarter',
                    'date_from': '2017-07-01',
                    'date_to': '2017-09-30',
                },
                {
                    'string': 'Apr - Jun 2017',
                    'period_type': 'quarter',
                    'date_from': '2017-04-01',
                    'date_to': '2017-06-30',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_quarter'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'Oct - Dec 2016',
                    'period_type': 'quarter',
                    'date_from': '2016-10-01',
                    'date_to': '2016-12-31',
                },
                {
                    'string': 'Oct - Dec 2015',
                    'period_type': 'quarter',
                    'date_from': '2015-10-01',
                    'date_to': '2015-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_quarter'}, 'comparison': {'filter': 'custom', 'date_from': '2016-10-01', 'date_to': '2016-12-31'}},
            [
                {
                    'string': 'Oct - Dec 2016',
                    'period_type': 'quarter',
                    'date_from': '2016-10-01',
                    'date_to': '2016-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_fiscalyear_range_full_year(self):
        ''' Test the filter_date with 'this_year'/'last_year' in 'range' mode when the fiscal year ends the 12-31.'''
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}},
            {
                'string': '2017',
                'period_type': 'year',
                'date_from': '2017-01-01',
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'previous_year'}},
            {
                'string': '2016',
                'period_type': 'year',
                'date_from': '2016-01-01',
                'date_to': '2016-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'next_year'}},
            {
                'string': '2018',
                'period_type': 'year',
                'date_from': '2018-01-01',
                'date_to': '2018-12-31',
            },
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': '2016',
                    'period_type': 'year',
                    'date_from': '2016-01-01',
                    'date_to': '2016-12-31',
                },
                {
                    'string': '2015',
                    'period_type': 'year',
                    'date_from': '2015-01-01',
                    'date_to': '2015-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': '2016',
                    'period_type': 'year',
                    'date_from': '2016-01-01',
                    'date_to': '2016-12-31',
                },
                {
                    'string': '2015',
                    'period_type': 'year',
                    'date_from': '2015-01-01',
                    'date_to': '2015-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'custom', 'date_from': '2016-01-01', 'date_to': '2016-12-31'}},
            [
                {
                    'string': '2016',
                    'period_type': 'year',
                    'date_from': '2016-01-01',
                    'date_to': '2016-12-31',
                },
            ],
        )

    @freeze_time('2024-06-15')
    def test_filter_comparison_custom_default_date_capped_to_today(self):
        ''' The default 'custom' comparison range must not extend into the future: for a 'this_year'
        report queried before year-end, it should be capped to today instead of the report's date_to. '''
        options = self.date_range_report.get_options({'date': {'default_opening_date': 'this_year'}})

        self.assertEqual(options['date']['date_to'], '2024-12-31')
        self.assertEqual(
            options['comparison']['date_to'], '2024-06-15',
            "The default comparison range must be capped to today, not the report's future date_to.",
        )
        self.assertEqual(
            options['comparison']['date_from'], '2024-01-01',
            "The default comparison range must start at the beginning of the fiscal year containing today.",
        )

    @freeze_time('2017-12-31')
    def test_filter_date_fiscalyear_range_overlap_years(self):
        ''' Test the filter_date with 'this_year'/'last_year' in 'range' mode when the fiscal year overlaps 2 years.'''
        self.env.company.fiscalyear_last_day = 30
        self.env.company.fiscalyear_last_month = '6'

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}},
            {
                'string': 'Jul 2017 - Jun 2018',
                'period_type': 'year',
                'date_from': '2017-07-01',
                'date_to': '2018-06-30',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'previous_year'}},
            {
                'string': 'Jul 2016 - Jun 2017',
                'period_type': 'year',
                'date_from': '2016-07-01',
                'date_to': '2017-06-30',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'next_year'}},
            {
                'string': 'Jul 2018 - Jun 2019',
                'period_type': 'year',
                'date_from': '2018-07-01',
                'date_to': '2019-06-30',
            },
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'Jul 2016 - Jun 2017',
                    'period_type': 'year',
                    'date_from': '2016-07-01',
                    'date_to': '2017-06-30',
                },
                {
                    'string': 'Jul 2015 - Jun 2016',
                    'period_type': 'year',
                    'date_from': '2015-07-01',
                    'date_to': '2016-06-30',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'Jul 2016 - Jun 2017',
                    'period_type': 'year',
                    'date_from': '2016-07-01',
                    'date_to': '2017-06-30',
                },
                {
                    'string': 'Jul 2015 - Jun 2016',
                    'period_type': 'year',
                    'date_from': '2015-07-01',
                    'date_to': '2016-06-30',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'custom', 'date_from': '2016-07-01', 'date_to': '2017-06-30'}},
            [
                {
                    'string': 'Jul 2016 - Jun 2017',
                    'period_type': 'year',
                    'date_from': '2016-07-01',
                    'date_to': '2017-06-30',
                },
            ],
        )

    @freeze_time('2025-12-31')
    def test_filter_date_custom_with_fy(self):
        # Set fiscal year end to 31th March
        self.env.company.fiscalyear_last_month = '3'

        # Single date reports
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'period_type': 'custom', 'date_to': '2025-12-31'}},
            {
                'string': 'As of 12/31/2025',
                'period_type': 'month',
                'fallback_from': 'custom',
                'date_from': None,
                'date_to': '2025-12-31',
            },
        )
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'period_type': 'custom', 'date_to': '2025-03-31'}},
            {
                'string': 'As of 03/31/2025',
                'period_type': 'year',
                'fallback_from': 'custom',
                'date_from': None,
                'date_to': '2025-03-31',
            },
        )

        self.single_date_report.use_fiscal_periods = False
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'period_type': 'custom', 'date_to': '2025-12-31'}},
            {
                'string': 'As of 12/31/2025',
                'period_type': 'year',
                'fallback_from': 'custom',
                'date_from': None,
                'date_to': '2025-12-31',
            },
        )
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'period_type': 'custom', 'date_to': '2025-03-31'}},
            {
                'string': 'As of 03/31/2025',
                'period_type': 'month',
                'fallback_from': 'custom',
                'date_from': None,
                'date_to': '2025-03-31',
            },
        )

        # Range reports
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'period_type': 'custom', 'date_from': '2025-01-01', 'date_to': '2025-12-31'}},
            {
                'string': 'Jan 2025 - Dec 2025',
                'period_type': 'custom',
                'date_from': '2025-01-01',
                'date_to': '2025-12-31',
            },
        )
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'period_type': 'custom', 'date_from': '2024-04-01', 'date_to': '2025-03-31'}},
            {
                'string': 'Apr 2024 - Mar 2025',
                'period_type': 'year',
                'fallback_from': 'custom',
                'date_from': '2024-04-01',
                'date_to': '2025-03-31',
            },
        )

        self.date_range_report.use_fiscal_periods = False
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'period_type': 'custom', 'date_from': '2025-01-01', 'date_to': '2025-12-31'}},
            {
                'string': '2025',
                'period_type': 'year',
                'fallback_from': 'custom',
                'date_from': '2025-01-01',
                'date_to': '2025-12-31',
            },
        )
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'period_type': 'custom', 'date_from': '2024-04-01', 'date_to': '2025-03-31'}},
            {
                'string': 'Apr 2024 - Mar 2025',
                'period_type': 'custom',
                'date_from': '2024-04-01',
                'date_to': '2025-03-31',
            },
        )

    @freeze_time('2025-12-31')
    def test_filter_date_fiscalyear_range_custom_years(self):
        ''' Test the filter_date with 'this_year'/'last_year' in 'range' mode with custom account.fiscal.year records. It should also handle gaps between custom FY'''
        custom_ranges = [
            ('2024-02-14', '2024-12-31', 'FY 2024_2'),
            ('2025-01-01', '2025-04-30', 'FY 2025_1'),
            ('2025-05-01', '2025-12-31', 'FY 2025_2'),
            ('2026-05-01', '2026-06-30', 'FY 2026_2'),
        ]

        for custom_range in custom_ranges:
            self.env['account.fiscal.year'].create({
                'name': custom_range[2],
                'date_from': custom_range[0],
                'date_to': custom_range[1],
                'company_id': self.env.company.id,
            })

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'prev_year'}},
            {
                'string': 'FY 2025_1',
                'period_type': 'year',
                'date_from': '2025-01-01',
                'date_to': '2025-04-30',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'this_year'}},
            {
                'string': 'FY 2025_2',
                'period_type': 'year',
                'date_from': '2025-05-01',
                'date_to': '2025-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'default_opening_date': 'next_year'}},
            {
                'string': 'Jan 2026 - Apr 2026',
                'period_type': 'year',
                'date_from': '2026-01-01',
                'date_to': '2026-04-30',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'period_type': 'year', 'date_to': '2024-06-14'}},
            {
                'string': 'FY 2024_2',
                'period_type': 'year',
                'date_from': '2024-02-14',
                'date_to': '2024-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'period_type': 'year', 'date_to': '2024-01-14'}},
            {
                'string': '01/01/2024 - 02/13/2024',
                'period_type': 'year',
                'date_from': '2024-01-01',
                'date_to': '2024-02-13',
            },
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {
                'date': {'default_opening_date': 'next_year'},
                'comparison': {'filter': 'previous_period', 'number_period': 3},
            },
            [
                {
                    'string': 'FY 2025_2',
                    'period_type': 'year',
                    'date_from': '2025-05-01',
                    'date_to': '2025-12-31',
                },
                {
                    'string': 'FY 2025_1',
                    'period_type': 'year',
                    'date_from': '2025-01-01',
                    'date_to': '2025-04-30',
                },
                {
                    'string': 'FY 2024_2',
                    'period_type': 'year',
                    'date_from': '2024-02-14',
                    'date_to': '2024-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {
                'date': {'default_opening_date': 'this_year'},
                'comparison': {'filter': 'same_last_year', 'number_period': 2},
            },
            [
                {
                    'string': 'May 2024 - Dec 2024',
                    'period_type': 'year',
                    'date_from': '2024-05-01',
                    'date_to': '2024-12-31',
                },
                {
                    'string': 'May 2023 - Dec 2023',
                    'period_type': 'year',
                    'date_from': '2023-05-01',
                    'date_to': '2023-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_custom_range(self):
        ''' Test the filter_date with a custom dates range.'''
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'date_from': '2017-01-01', 'date_to': '2017-01-15'}},
            {
                'string': '%s - %s' % (format_date(self.env, '2017-01-01'), format_date(self.env, '2017-01-15')),
                'period_type': 'custom',
                'date_from': '2017-01-01',
                'date_to': '2017-01-15',
            },
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {
                'date': {'date_from': '2017-01-01', 'date_to': '2017-01-15'},
                'comparison': {'filter': 'previous_period', 'number_period': 2},
            },
            [
                {
                    'string': '2016',
                    'period_type': 'year',
                    'date_from': '2016-01-01',
                    'date_to': '2016-12-31',
                },
                {
                    'string': '2015',
                    'period_type': 'year',
                    'date_from': '2015-01-01',
                    'date_to': '2015-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.date_range_report,
            {
                'date': {'date_from': '2017-01-01', 'date_to': '2017-01-15'},
                'comparison': {'filter': 'same_last_year', 'number_period': 2},
            },
            [
                {
                    'string': '%s - %s' % (format_date(self.env, '2016-01-01'), format_date(self.env, '2016-01-15')),
                    'period_type': 'custom',
                    'date_from': '2016-01-01',
                    'date_to': '2016-01-15',
                },
                {
                    'string': '%s - %s' % (format_date(self.env, '2015-01-01'), format_date(self.env, '2015-01-15')),
                    'period_type': 'custom',
                    'date_from': '2015-01-01',
                    'date_to': '2015-01-15',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_custom_range_recognition(self):
        ''' Test the period is well recognized when dealing with custom dates range.
        It means date_from = '2018-01-01', date_to = '2018-12-31' must be considered as a full year.
        '''
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'date_from': '2017-12-01', 'date_to': '2017-12-31'}},
            {
                'string': 'Dec 2017',
                'period_type': 'month',
                'fallback_from': 'custom',
                'date_from': '2017-12-01',
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'date_from': '2017-10-01', 'date_to': '2017-12-31'}},
            {
                'string': 'Oct - Dec 2017',
                'period_type': 'quarter',
                'fallback_from': 'custom',
                'date_from': '2017-10-01',
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_date(
            self.date_range_report,
            {'date': {'date_from': '2017-01-01', 'date_to': '2017-12-31'}},
            {
                'string': '2017',
                'period_type': 'year',
                'fallback_from': 'custom',
                'date_from': '2017-01-01',
                'date_to': '2017-12-31',
            },
        )

        self.env.company.fiscalyear_last_day = 30
        self.env.company.fiscalyear_last_month = '6'
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'date_from': '2016-07-01', 'date_to': '2017-06-30'}},
            {
                'string': 'Jul 2016 - Jun 2017',
                'period_type': 'year',
                'fallback_from': 'custom',
                'date_from': '2016-07-01',
                'date_to': '2017-06-30',
            },
        )

        self.env['account.fiscal.year'].create({
            'name': 'custom 0',
            'date_from': '2017-10-01',
            'date_to': '2017-12-31',
            'company_id': self.env.company.id,
        })
        self._assert_filter_date(
            self.date_range_report,
            {'date': {'date_from': '2017-10-01', 'date_to': '2017-12-31'}},
            {
                'string': 'custom 0',
                'period_type': 'year',
                'fallback_from': 'custom',
                'date_from': '2017-10-01',
                'date_to': '2017-12-31',
            },
        )

    ####################################################
    # SINGLE DATE
    ####################################################

    @freeze_time('2017-12-30')
    def test_filter_date_today_single(self):
        ''' Test the filter_date with 'today' in 'single' mode.'''
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'default_opening_date': 'today'}},
            {
                'string': 'As of %s' % format_date(self.env, '2017-12-30'),
                'period_type': 'today',
                'date_from': None,
                'date_to': '2017-12-30',
            },
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'today'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2016-12-31',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2015-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2015-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'today'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-30'),
                    'period_type': 'today',
                    'date_from': None,
                    'date_to': '2016-12-30',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2015-12-30'),
                    'period_type': 'today',
                    'date_from': None,
                    'date_to': '2015-12-30',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'today'}, 'comparison': {'filter': 'custom', 'date_to': '2016-12-31'}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2016-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_month_single(self):
        ''' Test the filter_date with 'this_month'/'last_month' in 'single' mode.'''
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_month'}},
            {
                'string': 'As of %s' % format_date(self.env, '2017-12-31'),
                'period_type': 'month',
                'date_from': None,
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_month'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2017-11-30'),
                    'period_type': 'month',
                    'date_from': None,
                    'date_to': '2017-11-30',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2017-10-31'),
                    'period_type': 'month',
                    'date_from': None,
                    'date_to': '2017-10-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_month'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-31'),
                    'period_type': 'month',
                    'date_from': None,
                    'date_to': '2016-12-31',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2015-12-31'),
                    'period_type': 'month',
                    'date_from': None,
                    'date_to': '2015-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_quarter_single(self):
        ''' Test the filter_date with 'this_quarter'/'last_quarter' in 'single' mode.'''
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_quarter'}},
            {
                'string': 'As of %s' % format_date(self.env, '2017-12-31'),
                'period_type': 'quarter',
                'date_from': None,
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_quarter'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2017-09-30'),
                    'period_type': 'quarter',
                    'date_from': None,
                    'date_to': '2017-09-30',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2017-06-30'),
                    'period_type': 'quarter',
                    'date_from': None,
                    'date_to': '2017-06-30',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_quarter'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-31'),
                    'period_type': 'quarter',
                    'date_from': None,
                    'date_to': '2016-12-31',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2015-12-31'),
                    'period_type': 'quarter',
                    'date_from': None,
                    'date_to': '2015-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_fiscalyear_single_full_year(self):
        ''' Test the filter_date with 'this_year'/'last_year' in 'single' mode when the fiscal year ends the 12-31.'''
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}},
            {
                'string': 'As of %s' % format_date(self.env, '2017-12-31'),
                'period_type': 'year',
                'date_from': None,
                'date_to': '2017-12-31',
            },
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2016-12-31',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2015-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2015-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2016-12-31',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2015-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2015-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_fiscalyear_single_overlap_years(self):
        ''' Test the filter_date with 'this_year'/'last_year' in 'single' mode when the fiscal year overlaps 2 years.'''
        self.env.company.fiscalyear_last_day = 30
        self.env.company.fiscalyear_last_month = '6'

        self._assert_filter_date(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}},
            {
                'string': 'As of %s' % format_date(self.env, '2018-06-30'),
                'period_type': 'year',
                'date_from': None,
                'date_to': '2018-06-30',
            },
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2017-06-30'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2017-06-30',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2016-06-30'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2016-06-30',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2017-06-30'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2017-06-30',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2016-06-30'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2016-06-30',
                },
            ],
        )

    @freeze_time('2025-12-31')
    def test_filter_date_fiscalyear_single_custom_years(self):
        ''' Test the filter_date with 'this_year'/'last_year' in 'single' mode with custom account.fiscal.year records.'''
        custom_ranges = [
            ('2024-02-14', '2024-12-31', 'FY 2024_2'),
            ('2025-01-01', '2025-04-30', 'FY 2025_1'),
            ('2025-05-01', '2025-12-31', 'FY 2025_2'),
            ('2026-05-01', '2026-06-30', 'FY 2026_2'),
        ]

        for custom_range in custom_ranges:
            self.env['account.fiscal.year'].create({
                'name': custom_range[2],
                'date_from': custom_range[0],
                'date_to': custom_range[1],
                'company_id': self.env.company.id,
            })

        self._assert_filter_date(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}},
            {
                'string': 'FY 2025_2',
                'period_type': 'year',
                'date_from': None,
                'date_to': '2025-12-31',
            },
        )

        with freeze_time('2026-05-01'):
            self._assert_filter_date(
                self.single_date_report,
                {'date': {'default_opening_date': 'this_year'}},
                {
                    'string': 'FY 2026_2',
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2026-06-30',
                },
            )

        self._assert_filter_date(
            self.single_date_report,
            {'date': {'period_type': 'year', 'date_to': '2024-01-01'}},
            {
                'string': 'As of 02/13/2024',
                'period_type': 'year',
                'date_from': None,
                'date_to': '2024-02-13',
            },
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'FY 2025_1',
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2025-04-30',
                },
                {
                    'string': 'FY 2024_2',
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2024-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'default_opening_date': 'this_year'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'As of 12/31/2024',
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2024-12-31',
                },
                {
                    'string': 'As of 12/31/2023',
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2023-12-31',
                },
            ],
        )

    @freeze_time('2017-12-31')
    def test_filter_date_custom_single(self):
        ''' Test the filter_date with a custom date in 'single' mode.'''
        self._assert_filter_date(
            self.single_date_report,
            {'date': {'date_to': '2018-01-15'}},
            {
                'string': 'As of %s' % format_date(self.env, '2018-01-15'),
                'period_type': 'custom',
                'date_from': None,
                'date_to': '2018-01-15',
            },
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'date_to': '2018-01-15'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2017-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2017-12-31',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2016-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2016-12-31',
                },
            ],
        )

        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'date_to': '2018-01-15'}, 'comparison': {'filter': 'same_last_year', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2017-01-15'),
                    'period_type': 'custom',
                    'date_from': None,
                    'date_to': '2017-01-15',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2016-01-15'),
                    'period_type': 'custom',
                    'date_from': None,
                    'date_to': '2016-01-15',
                },
            ],
        )

    @freeze_time('2021-09-01')
    def test_filter_date_custom_single_period_type_month(self):
        ''' Test the filter_date with a custom date in 'single' mode.'''
        self._assert_filter_comparison(
            self.single_date_report,
            {'date': {'date_to': '2019-07-18'}, 'comparison': {'filter': 'previous_period', 'number_period': 2}},
            [
                {
                    'string': 'As of %s' % format_date(self.env, '2018-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2018-12-31',
                },
                {
                    'string': 'As of %s' % format_date(self.env, '2017-12-31'),
                    'period_type': 'year',
                    'date_from': None,
                    'date_to': '2017-12-31',
                },
            ],
        )

    ####################################################
    # User Defined Filters on Journal Items
    ####################################################

    @freeze_time('2023-09-01')
    def test_filter_aml_ir_filters(self):
        # Test user-defined filter set on journal items used as report options

        filter_record = self.env['ir.filters'].create({
            'model_id': 'account.move.line',
            'user_ids': [self.uid],
            'name': 'To Check',
            'domain': '[("move_id.review_state", "in", ("todo", "anomaly"))]',
        })

        report = self.env['account.report'].create({
            'name': 'Test ir filters',
            'filter_aml_ir_filters': True,
            'root_report_id': self.env.ref("account_reports.profit_and_loss").id,
            'column_ids': [
                Command.create({
                    'name': 'Balance',
                    'expression_label': 'balance',
                }),
            ],
            'line_ids': [
                Command.create({
                    'name': 'Line 1',
                    'expression_ids': [
                        Command.create({
                            'label': 'balance',
                            'engine': 'domain',
                            'formula': '[("account_id.account_type", "=", "income")]',
                            'subformula': '-sum',
                        }),
                    ],
                }),
            ],
        })

        moves = (
                self.init_invoice("out_invoice", self.partner_a, "2023-09-01", amounts=[1000])
                + self.init_invoice("out_invoice", self.partner_a, "2023-09-01", amounts=[1000])
        )
        moves.action_post()
        moves[0].review_state = 'todo'

        options = self._generate_options(report, '2023-01-01', '2023-12-31')

        for opt in options['aml_ir_filters']:
            if opt['id'] == filter_record.id:
                opt['selected'] = True
                break

        # Ensure that only the move with the 'checked' at false attribute is included in the report
        self.assertLinesValues(
            report._get_lines(options),
            #      Name   Balance
            [       0,      1],
            [
                ('Line 1', 1000)
            ],
            options
        )

    def test_hide_line_at_0_tour(self):
        report = self.env.ref('account_reports.balance_sheet')
        report.filter_hide_0_lines = 'optional'
        self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'date': '2020-0%s-15' % i,
            'invoice_date': '2020-0%s-15' % i,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, self.tax_sale_a.ids)],
            })],
        } for i in range(1, 4)]).action_post()

        self.start_tour("/odoo/action-account_reports.action_account_report_bs", 'account_reports_hide_0_lines', login=self.env.user.login)

    @freeze_time('2020-01-16')
    def test_hide_line_at_0_tour_with_string_columns(self):
        report = self.env.ref('account_reports.general_ledger_report')
        report.filter_hide_0_lines = 'optional'
        self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2020-01-15',
            'line_ids': [Command.create({
                'partner_id': self.partner_a.id,
                'debit': 0.0,
                'credit': 0.0,
                'name': "Coucou les biloutes",
                'account_id': self.company_data['default_account_payable'].id,
                'journal_id': self.company_data['default_journal_misc'].id,
            })],
        }).action_post()

        self.start_tour("/odoo/action-account_reports.action_account_report_general_ledger", 'account_reports_hide_0_lines_with_string_columns', login=self.env.user.login)

    def test_rounding_unit_tour(self):
        self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'date': '2023-01-01',
            'invoice_date': '2023-01-01',
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'price_unit': 1000000.0,
                'tax_ids': [Command.set(self.tax_sale_a.ids)],
            })],
        }).action_post()

        self.start_tour("/odoo/action-account_reports.action_account_report_bs", 'account_reports_rounding_unit', login=self.env.user.login)

    def test_filter_multi_company(self):
        def _check_company_filter(allowed_companies, expected_companies, message=None, match_active=True):
            options = self.single_date_report.with_context(allowed_company_ids=allowed_companies.ids).get_options({})
            computed_company_ids = self.env['account.report'].get_report_company_ids(options)
            if match_active:
                # Active company should match
                self.assertEqual(computed_company_ids[0], expected_companies[0].id, message)
            # Selected companies should match, whatever their order
            self.assertEqual(set(computed_company_ids), set(expected_companies.ids), message)

        main_company = self.company_data['company']
        main_company.vat = '123'
        branch_1 = self.env['res.company'].create({'name': "Branch 1", 'parent_id': main_company.id, 'vat': '123'})
        branch_1_1 = self.env['res.company'].create({'name': "Branch 1 sub-branch 1", 'parent_id': branch_1.id})
        branch_1_2 = self.env['res.company'].create({'name': "Branch 1 sub-branch 2", 'parent_id': branch_1.id, 'vat': '123'})
        branch_2 = self.env['res.company'].create({'name': "Branch 2", 'parent_id': main_company.id})
        branch_2_1 = self.env['res.company'].create({'name': "Branch 2 sub-branch 1", 'parent_id': branch_2.id})
        other_company = self.env['res.company'].create({'name': "Other company"})

        # Test 'tax_units' when no tax unit is defined and VAT is shared
        self.single_date_report.filter_multi_company = 'tax_units'

        _check_company_filter(
            main_company + branch_1 + branch_1_1 + branch_1_2 + branch_2 + branch_2_1 + other_company,
            main_company + branch_1 + branch_1_1 + branch_1_2 + branch_2 + branch_2_1,
            "The main company and all of its sub-branches should be selected",
        )
        _check_company_filter(
            branch_1 + main_company + branch_1_1 + branch_1_2 + branch_2 + branch_2_1 + other_company,
            branch_1 + branch_1_1 + branch_1_2,
            "When the active company is a branch of another active company, it should only be selected with its sub-branches.",
        )
        _check_company_filter(
            main_company + branch_1 + branch_1_2 + branch_2_1 + other_company,
            main_company + branch_1 + branch_1_2 + branch_2_1,
            "Choosing a subset of branches in the company selector should keep that selection in the report.",
        )

        # Test 'selector' filter
        self.single_date_report.filter_multi_company = 'selector'

        _check_company_filter(
            branch_1,
            branch_1,
        )
        _check_company_filter(
            main_company + branch_1 + branch_1_1 + branch_1_2 + branch_2 + branch_2_1 + other_company,
            main_company + branch_1 + branch_1_1 + branch_1_2 + branch_2 + branch_2_1 + other_company,
        )
        _check_company_filter(
            branch_1 + main_company + branch_1_1 + branch_1_2 + branch_2 + branch_2_1 + other_company,
            branch_1 + main_company + branch_1_1 + branch_1_2 + branch_2 + branch_2_1 + other_company,
        )
        _check_company_filter(
            main_company + branch_1_1 + branch_1_2 + branch_2 + other_company,
            main_company + branch_1_1 + branch_1_2 + branch_2 + other_company,
        )

        # Test 'tax_units' filter, with no tax unit, and non-shared VAT numbers
        self.single_date_report.filter_multi_company = 'tax_units'
        branch_1_1.vat = '456'
        branch_2.vat = '789'

        _check_company_filter(
            main_company + branch_1_1 + branch_1_2 + branch_2 + branch_2_1 + other_company,
            main_company + branch_1_2,
            "Only the current company and its sub-branches sharing its vat number should be selected.",
        )

        _check_company_filter(
            branch_2 + main_company + branch_1_1 + branch_1_2  + branch_2_1 + other_company,
            branch_2 + branch_2_1,
            "Only the current company and its sub-branches sharing its vat number should be selected.",
        )

        # Test 'tax_units' filter, with an existing tax unit object
        self.single_date_report.country_id = self.env.ref('base.be')
        self.single_date_report.availability_condition = 'country'

        tax_unit = self.env['account.tax.unit'].create({
            'name': "Test Tax Unit",
            'country_id': self.single_date_report.country_id.id,
            'vat': 'BE0477472701',
            'company_ids': (main_company + branch_1_1 + branch_1_2 + branch_2 + other_company).ids,
            'main_company_id': main_company.id,
        })

        _check_company_filter(
            other_company + main_company + branch_1_1 + branch_1_2 + branch_2,
            other_company + main_company + branch_1_1 + branch_1_2 + branch_2,
            "Opening the report with a company selector matching the content of the tax unit should select this tax unit, keeping the companies.",
            match_active=False,
        )

        _check_company_filter(
            main_company | tax_unit.company_ids + branch_2_1,
            main_company + branch_1_2,
            "Opening the report with a company selector matching more than the content of the tax unit should not select the tax unit, "
            "but take the accessible branches with the same VAT number as the active company.",
        )

        _check_company_filter(
            main_company + branch_1_1 + branch_1_2 + branch_2,
            main_company + branch_1_2,
            "Opening the report with a company selector matching less than the content of the tax unit should select the active sub-branches "
            "with the same VAT as the active company.",
        )

        # Test 'tax_units' filter, with no tax unit, and no VAT number on branches (only one on main company)
        branch_1.vat = None
        branch_1_1.vat = None
        branch_1_2.vat = None
        branch_2.vat = None

        _check_company_filter(
            branch_2 + branch_2_1,
            branch_2 + branch_2_1,
            "When no VAT exists in the hierarchy; all companies should be considered as sharing the same VAT, and active companies should be kept.",
        )

        _check_company_filter(
            branch_2_1 + branch_2,
            branch_2_1 + branch_2,
            "When no VAT exists in the hierarchy; all companies should be considered as sharing the same VAT, and active companies should be kept.",
        )

    @freeze_time('2017-12-31')
    def test_period_order(self):
        report = self.date_range_report
        previous_options = {'date': {'default_opening_date': 'this_year', 'mode': 'range'}, 'comparison': {'filter': 'same_last_year', 'number_period': 1, 'period_order': 'descending'}}
        options = report.get_options(previous_options)

        expected_values = [
            {
                'name': '2017',
                 'forced_options': {
                    'date': {'string': '2017', 'period_type': 'year', 'date_from': '2017-01-01', 'date_to': '2017-12-31'}
                 }
            },
            {
                'name': '2016',
                'forced_options': {
                    'date': {'string': '2016', 'period_type': 'year', 'date_from': '2016-01-01', 'date_to': '2016-12-31'}
                }
            },
        ]

        for i, val in enumerate(expected_values):
            self.assertDictEqual(options['column_headers'][0][i], val)

        previous_options['comparison']['period_order'] = 'ascending'
        new_options = report.get_options(previous_options)
        new_expected_values = expected_values[::-1]

        for i, val in enumerate(new_expected_values):
            self.assertDictEqual(new_options['column_headers'][0][i], val)

    ####################################################
    # DATES RANGE
    ####################################################

    @freeze_time('2024-09-01')
    def test_returns_period_filter(self):
        generic_tax_report = self.env.ref('account.generic_tax_report')

        # l10n_us_reports adds a return type for this report; we make sure that none is set at this point, for testing purposes
        generic_tax_report.return_type_ids.unlink()

        # When the tax report isn't linked to a return type, it should fallback on 'this_month'
        self._assert_filter_date(
            generic_tax_report,
            {'no_report_reroute': True},
            {
                'string': 'Sep 2024',
                'period_type': 'month',
                'date_from': '2024-09-01',
                'date_to': '2024-09-30',
            },
        )

        # Assigning a return type without periodicity should now make use of the periodicity set on the company (monthly, by default),
        return_type = self.env['account.return.type'].create({
            'name': "Zaphod Beeblebrox",
            'report_id': generic_tax_report.id,
        })

        self._assert_filter_date(
            generic_tax_report,
            {'no_report_reroute': True},
            {
                'string': 'Aug 2024',
                'period_type': 'month',
                'date_from': '2024-08-01',
                'date_to': '2024-08-31',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': fields.Date.today() + relativedelta(months=-8), 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Jan 2024',
                'period_type': 'month',
                'date_from': '2024-01-01',
                'date_to': '2024-01-31',
            },
        )

        self.env.company.account_return_periodicity = 'year'

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'default_opening_date': 'previous_return_period'}, 'no_report_reroute': True},
            {
                'string': '2023',
                'period_type': 'year',
                'date_from': '2023-01-01',
                'date_to': '2023-12-31',
            },
        )

        self.env.company.fiscalyear_last_day = 31
        self.env.company.fiscalyear_last_month = '5'

        # Tax report has the filter use_fiscal_periods set to False, so it should not take the fiscal years dates into account.
        self._assert_filter_date(
            generic_tax_report,
            {'date': {'default_opening_date': 'previous_return_period'}, 'no_report_reroute': True},
            {
                'string': '2023',
                'period_type': 'year',
                'date_from': '2023-01-01',
                'date_to': '2023-12-31',
            },
        )

        # Setting a periodicity on the return type should take precedence over the company setting
        return_type.deadline_periodicity = 'semester'

        self._assert_filter_date(
            generic_tax_report,
            {'no_report_reroute': True},
            {
                'string': 'Jan 2024 - Jun 2024',
                'period_type': 'return_period',
                'date_from': '2024-01-01',
                'date_to': '2024-06-30',
            },
        )

        # Check filter fallback
        return_type.deadline_periodicity = 'monthly'

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2024-08-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Aug 2024',
                'period_type': 'month',
                'date_from': '2024-08-01',
                'date_to': '2024-08-31',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2023-08-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Aug 2023',
                'period_type': 'month',
                'date_from': '2023-08-01',
                'date_to': '2023-08-31',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2021-08-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Aug 2021',
                'period_type': 'month',
                'date_from': '2021-08-01',
                'date_to': '2021-08-31',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2025-08-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Aug 2025',
                'period_type': 'month',
                'date_from': '2025-08-01',
                'date_to': '2025-08-31',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2025-02-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Feb 2025',
                'period_type': 'month',
                'date_from': '2025-02-01',
                'date_to': '2025-02-28',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2024-12-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Dec 2024',
                'period_type': 'month',
                'date_from': '2024-12-01',
                'date_to': '2024-12-31',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2023-11-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Nov 2023',
                'period_type': 'month',
                'date_from': '2023-11-01',
                'date_to': '2023-11-30',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2023-03-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Mar 2023',
                'period_type': 'month',
                'date_from': '2023-03-01',
                'date_to': '2023-03-31',
            },
        )

        return_type.deadline_periodicity = 'trimester'
        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2023-03-01', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Jan - Mar 2023',
                'period_type': 'quarter',
                'date_from': '2023-01-01',
                'date_to': '2023-03-31',
            },
        )

        self._assert_filter_date(
            generic_tax_report,
            {'date': {'date_to': '2022-12-31', 'period_type': 'return_period'}, 'no_report_reroute': True},
            {
                'string': 'Oct - Dec 2022',
                'period_type': 'quarter',
                'date_from': '2022-10-01',
                'date_to': '2022-12-31',
            },
        )

    ####################################################
    # CONSOLIDATION
    ####################################################

    def test_filter_consolidation(self):
        company1 = self.company_data['company']
        company2 = self.company_data_2['company']
        self.env['res.currency.rate'].search([]).unlink()
        self.company_data_2['default_account_receivable'].with_company(company1).code = '121000'
        self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2024-06-06',
            'invoice_line_ids': [Command.create({
                'price_unit': 50,
            })],
            'company_id': company1.id,
        }).action_post()
        self.env['account.move'].with_company(company2).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2024-06-06',
            'invoice_line_ids': [Command.create({
                'price_unit': 50,
            })],
            'company_id': company2.id,
        }).action_post()

        report = self.env['account.report'].create({
            'name': "Simple Report",
            'filter_multi_company': 'selector',
            'filter_account_type': 'both',
            'column_ids': [Command.create({
                'name': 'Balance',
                'expression_label': 'balance',
            })],
            'line_ids': [Command.create({
                'name': "The line",
                'groupby': 'account_id',
                'foldability': 'always_unfolded',
                'expression_ids': [Command.create({
                    'label': 'balance',
                    'engine': 'domain',
                    'formula': [],
                    'subformula': 'sum',
                })],
            })],
        })
        options = self._generate_options(report, '2024-01-01', '2024-12-31')
        self.assertLinesValues(
            report._get_lines(options),
            [0, 1],
            [
                ('The line', 100),
                ('121000 Accounts Receivable', 50),
                ('121000 Accounts Receivable', 50),
                ('Total The line', 100)
            ],
            options,
        )

        options['consolidation'] = True
        self.assertLinesValues(
            report._get_lines(options),
            [0, 1],
            [
                ('The line', 100),
                ('121000 Accounts Receivable', 100),
                ('Total The line', 100)
            ],
            options,
        )

    def test_available_variants_options(self):
        # Ensure variants are visible in the variants selector if their availability condition is met
        def assert_available_variants_match(options, reports):
            expected_variants = [v['id'] for v in options.get('available_variants', [])]
            actual_reports = reports.mapped('id')

            self.assertEqual(
                expected_variants,
                actual_reports,
                msg=f"Expected available variants {expected_variants} but got {actual_reports}"
            )

        root_report = self.env['account.report'].create({
            'name': "Root Report",
            'allow_foreign_vat': True,
        })

        report_always = self.env['account.report'].create({
            'name': "Report Always available",
            'root_report_id': root_report.id,
        })

        report_generic_coa = self.env['account.report'].create({
            'name': "Report generic COA",
            'root_report_id': root_report.id,
            'availability_condition': 'coa',
            'chart_template': 'generic_coa',
        })

        report_us_country = self.env['account.report'].create({
            'name': "Report US country",
            'root_report_id': root_report.id,
            'availability_condition': 'country',
            'country_id': self.env.ref('base.us').id,
        })

        report_be_country = self.env['account.report'].create({
            'name': "Report BE country",
            'root_report_id': root_report.id,
            'availability_condition': 'country',
            'country_id': self.env.ref('base.be').id,
        })

        report_us_coa = self.env['account.report'].create({
            'name': "Report US COA",
            'root_report_id': root_report.id,
            'availability_condition': 'coa',
            'chart_template': 'us',
        })

        # Selecting Root Report
        options = self._generate_options(root_report, '2024-01-01', '2024-12-31')
        expected_reports = root_report + report_always + report_generic_coa + report_us_country
        assert_available_variants_match(options, expected_reports)

        # Selecting a child shouldn't change the order
        options = self._generate_options(report_always, '2024-01-01', '2024-12-31')
        assert_available_variants_match(options, expected_reports)

        self.env['account.fiscal.position'].create({
            'name': 'Test Fiscal Position',
            'auto_apply': True,
            'foreign_vat': 'BE980737405',
            'country_id': self.env.ref('base.be').id,
        })

        # Adding fiscal position should make BE-reports available since it allows foreign vat
        options = self._generate_options(root_report, '2024-01-01', '2024-12-31')
        assert_available_variants_match(options, expected_reports + report_be_country)

        (expected_reports + report_be_country).allow_foreign_vat = False
        options = self._generate_options(root_report, '2024-01-01', '2024-12-31')
        assert_available_variants_match(options, expected_reports)

        self.company_data['company'].chart_template = 'us'
        options = self._generate_options(root_report, '2024-01-01', '2024-12-31')
        assert_available_variants_match(options, root_report + report_always + report_us_coa + report_us_country)

        # only allow company 1 (US COA)
        self.env.user.company_ids = self.company_data['company']
        options = self._generate_options(root_report, '2024-01-01', '2024-12-31')
        assert_available_variants_match(options, root_report + report_always + report_us_coa + report_us_country)

        report_consolidation = self.env['account.report'].create({
            'name': "Report Consolidation",
            'root_report_id': root_report.id,
            'availability_condition': 'consolidation',
        })

        options = self._generate_options(root_report, '2024-01-01', '2024-12-31', default_options={'selected_variant_id': None})
        assert_available_variants_match(options, root_report + report_always + report_us_coa + report_us_country)
        self.assertEqual(options['selected_variant_id'], report_us_country.id)

        # Selecting a second company makes the consolidation variant available, and it becomes the default
        # variant to open, ahead of the still-matching country/coa variants.
        self.env.user.company_ids = self.company_data['company'] + self.company_data_2['company']
        options = self._generate_options(root_report, '2024-01-01', '2024-12-31', default_options={'selected_variant_id': None})
        assert_available_variants_match(options, root_report + report_always + report_us_coa + report_consolidation + report_us_country)
        self.assertEqual(options['selected_variant_id'], report_consolidation.id)

    def test_send_customer_statement_without_template(self):
        """Test sending the customer statement without an email template."""
        report = self.env.ref('account_reports.customer_statement_report')
        options = report.get_options({})
        options['partner_ids'] = [self.partner.id]

        wizard = self.env['account.report.send'].create({
            'account_report_id': report.id,
            'mail_subject': 'Customer Statement',
            'report_options': options,
        })
        self.assertEqual(wizard.mode, 'single')
        self.assertFalse(wizard.mail_template_id)

        wizard.action_send_and_print()

    def test_fiscalyear_end_on_feb_29(self):
        """Ensure that when the fiscal year ends on February 29, the reporting
        options correctly compute the start of the next fiscal period.
        """
        current_company = self.env.company
        current_company.write({'fiscalyear_last_day': 29, 'fiscalyear_last_month': '2'})
        report = self.env.ref('account_reports.customer_statement_report')
        options = report.get_options({})

        self.assertEqual(options['filter_date']['filters']['month']['start_day'], 1)
        self.assertEqual(options['filter_date']['filters']['month']['start_month'], 3)
