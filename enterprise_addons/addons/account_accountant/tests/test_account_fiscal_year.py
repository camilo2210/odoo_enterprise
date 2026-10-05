# -*- coding: utf-8 -*-
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo import fields


@tagged('post_install', '-at_install')
class TestFiscalPosition(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    def check_compute_fiscal_year(self, company, date, expected_date_from, expected_date_to):
        '''Compute the fiscal year at a certain date for the company passed as parameter.
        Then, check if the result matches the 'expected_date_from'/'expected_date_to' dates.

        :param company: The company.
        :param date: The date belonging to the fiscal year.
        :param expected_date_from: The expected date_from after computation.
        :param expected_date_to: The expected date_to after computation.
        '''
        current_date = fields.Date.from_string(date)
        res = company.compute_fiscalyear_dates(current_date)
        self.assertEqual(res['date_from'], fields.Date.from_string(expected_date_from))
        self.assertEqual(res['date_to'], fields.Date.from_string(expected_date_to))

    def test_default_fiscal_year(self):
        '''Basic case with a fiscal year xxxx-01-01 - xxxx-12-31.'''
        company = self.env.company
        company.fiscalyear_last_day = 31
        company.fiscalyear_last_month = '12'

        self.check_compute_fiscal_year(
            company,
            '2017-12-31',
            '2017-01-01',
            '2017-12-31',
        )

        self.check_compute_fiscal_year(
            company,
            '2017-01-01',
            '2017-01-01',
            '2017-12-31',
        )

    def test_leap_fiscal_year_1(self):
        '''Case with a leap year ending the 29 February.'''
        company = self.env.company
        company.fiscalyear_last_day = 29
        company.fiscalyear_last_month = '2'

        self.check_compute_fiscal_year(
            company,
            '2016-02-29',
            '2015-03-01',
            '2016-02-29',
        )

        self.check_compute_fiscal_year(
            company,
            '2015-03-01',
            '2015-03-01',
            '2016-02-29',
        )

    def test_leap_fiscal_year_2(self):
        '''Case with a leap year ending the 28 February.'''
        company = self.env.company
        company.fiscalyear_last_day = 28
        company.fiscalyear_last_month = '2'

        self.check_compute_fiscal_year(
            company,
            '2016-02-29',
            '2015-03-01',
            '2016-02-29',
        )

        self.check_compute_fiscal_year(
            company,
            '2016-03-01',
            '2016-03-01',
            '2017-02-28',
        )

    def test_custom_fiscal_year(self):
        '''Case with custom fiscal years.'''
        company = self.env.company
        company.fiscalyear_last_day = 31
        company.fiscalyear_last_month = '12'

        # Create custom fiscal year covering the 6 first months of 2017.
        self.env['account.fiscal.year'].create({
            'name': '6 month 2017',
            'date_from': '2017-01-01',
            'date_to': '2017-05-31',
            'company_id': company.id,
        })

        # Check before the custom fiscal year).
        self.check_compute_fiscal_year(
            company,
            '2017-02-01',
            '2017-01-01',
            '2017-05-31',
        )

        # Check after the custom fiscal year.
        self.check_compute_fiscal_year(
            company,
            '2017-11-01',
            '2017-06-01',
            '2017-12-31',
        )

        # Create custom fiscal year covering the 3 last months of 2017.
        self.env['account.fiscal.year'].create({
            'name': 'last 3 month 2017',
            'date_from': '2017-10-01',
            'date_to': '2017-12-31',
            'company_id': company.id,
        })

        # Check inside the custom fiscal years.
        self.check_compute_fiscal_year(
            company,
            '2017-07-01',
            '2017-06-01',
            '2017-09-30',
        )

    def test_sequencing_invoice(self):
        self.ensure_installed("account_fiscal_year")
        self.env['account.fiscal.year'].create([
            {
                'name': 'end 2024 - 2026',
                'date_from': '2024-12-01',
                'date_to': '2026-03-31',
                'company_id': self.company.id,
            },
            {
                'name': '2026 - 2027',
                'date_from': '2026-04-01',
                'date_to': '2027-12-31',
                'company_id': self.company.id,
            },
        ])
        for date, expected_name in [
            ('2024-12-04', 'INV/24-26/0001'),
            ('2025-05-15', 'INV/24-26/0002'),
            ('2026-03-15', 'INV/24-26/0003'),
            ('2026-04-15', 'INV/26-27/0001'),
            ('2027-01-01', 'INV/26-27/0001'),
            # Back to normal years
            ('2028-02-02', 'INV/2028/0001'),
        ]:
            move = self._create_invoice(date=date, journal=self.company_data['default_journal_sale'], post=True)
            self.assertEqual(move.name, expected_name)

    def test_fiscal_year_overlap_constrain(self):
        company = self.env.company

        self.env['account.fiscal.year'].create({
            'name': 'FY 2026',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'company_id': company.id
        })

        with self.assertRaises(ValidationError):
            self.env['account.fiscal.year'].create({
                'name': 'FY 2026 (invalid dates)',
                'date_from': '2026-01-01',
                'date_to': '2025-12-31',
                'company_id': company.id
            })

        with self.assertRaises(ValidationError):
            self.env['account.fiscal.year'].create({
                'name': 'FY 2026 (start overlap)',
                'date_from': '2026-05-01',
                'date_to': '2027-05-01',
                'company_id': company.id
            })

        with self.assertRaises(ValidationError):
            self.env['account.fiscal.year'].create({
                'name': 'FY 2026 (end overlap)',
                'date_from': '2025-05-01',
                'date_to': '2026-05-01',
                'company_id': company.id
            })

        with self.assertRaises(ValidationError):
            self.env['account.fiscal.year'].create({
                'name': 'FY 2026 (smaller year)',
                'date_from': '2026-05-01',
                'date_to': '2026-08-01',
                'company_id': company.id
            })

        with self.assertRaises(ValidationError):
            self.env['account.fiscal.year'].create({
                'name': 'FY 2026 (larger year)',
                'date_from': '2025-05-01',
                'date_to': '2027-08-01',
                'company_id': company.id
            })
