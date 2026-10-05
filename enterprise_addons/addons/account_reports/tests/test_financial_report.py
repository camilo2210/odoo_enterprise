# -*- coding: utf-8 -*-
# pylint: disable=C0326

import json

from .common import TestAccountReportsCommon

from odoo import fields, Command
from odoo.tests import tagged

from freezegun import freeze_time


@tagged('post_install', '-at_install')
class TestFinancialReport(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ==== Partners ====
        cls.partner_c = cls._create_partner(name='partner_c')

        # ==== Accounts ====

        # Cleanup existing "Current year earnings" accounts since we can only have one by company.
        cls.env['account.account'].search([
            ('company_ids', 'in', (cls.company_data['company'] + cls.company_data_2['company']).ids),
            ('account_type', '=', 'equity_unaffected'),
        ]).unlink()

        account_types = [
            'asset_receivable',
            'liability_payable',
            'asset_cash',
            'asset_current',
            'asset_prepayments',
            'asset_fixed',
            'asset_non_current',
            'equity',
            'equity_unaffected',
            'income',
        ]

        accounts = cls.env['account.account'].create([{
            'name': 'account%s' % i,
            'code': 'code%s' % i,
            'account_type': account_type,
        } for i, account_type in enumerate(account_types)])

        accounts_2 = cls.env['account.account'].create([{
            'name': 'account%s' % (i + 100),
            'code': 'code%s' % (i + 100),
            'account_type': account_type,
            'company_ids': [Command.link(cls.company_data_2['company'].id)]
        } for i, account_type in enumerate(account_types)])

        for account in accounts_2:
            account.code = account.with_company(cls.company_data_2['company']).code

        # ==== Custom filters ====

        cls.horizontal_group = cls.env['account.report.horizontal.group'].create({
            'name': 'Horizontal Group',
            'rule_ids': [
                Command.create({
                    'field_name': 'partner_id',
                    'domain': f"[('id', 'in', {(cls.partner_a + cls.partner_b).ids})]",
                }),
                Command.create({
                    'field_name': 'account_id',
                    'domain': f"[('id', 'in', {accounts[:2].ids})]",
                }),
            ],
        })

        # ==== Journal entries ====

        cls.move_2019 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2019-01-01'),
            'line_ids': [
                (0, 0, {'debit': 25.0,      'credit': 0.0,      'account_id': accounts[0].id,   'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 25.0,      'credit': 0.0,      'account_id': accounts[0].id,   'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 25.0,      'credit': 0.0,      'account_id': accounts[0].id,   'partner_id': cls.partner_c.id}),
                (0, 0, {'debit': 25.0,      'credit': 0.0,      'account_id': accounts[0].id,   'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 200.0,     'credit': 0.0,      'account_id': accounts[1].id,   'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 0.0,       'credit': 300.0,    'account_id': accounts[2].id,   'partner_id': cls.partner_c.id}),
                (0, 0, {'debit': 400.0,     'credit': 0.0,      'account_id': accounts[3].id,   'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,       'credit': 1100.0,   'account_id': accounts[4].id,   'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 700.0,     'credit': 0.0,      'account_id': accounts[6].id,   'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,       'credit': 800.0,    'account_id': accounts[7].id,   'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 800.0,     'credit': 0.0,      'account_id': accounts[8].id,   'partner_id': cls.partner_c.id}),
            ],
        })
        cls.move_2019.action_post()

        cls.move_2018 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2018-01-01'),
            'line_ids': [
                (0, 0, {'debit': 1000.0,    'credit': 0.0,      'account_id': accounts[0].id,   'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,       'credit': 1000.0,   'account_id': accounts[2].id,   'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 250.0,     'credit': 0.0,      'account_id': accounts[0].id,   'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,       'credit': 250.0,    'account_id': accounts[9].id,   'partner_id': cls.partner_a.id}),
            ],
        })
        cls.move_2018.action_post()

        cls.move_2017 = cls.env['account.move'].with_company(cls.company_data_2['company']).create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2017-01-01'),
            'line_ids': [
                (0, 0, {'debit': 2000.0,    'credit': 0.0,      'account_id': accounts_2[0].id, 'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,       'credit': 4000.0,   'account_id': accounts_2[2].id, 'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 0.0,       'credit': 5000.0,   'account_id': accounts_2[4].id, 'partner_id': cls.partner_c.id}),
                (0, 0, {'debit': 7000.0,    'credit': 0.0,      'account_id': accounts_2[6].id, 'partner_id': cls.partner_a.id}),
            ],
        })
        cls.move_2017.action_post()

        cls.report = cls.env.ref('account_reports.balance_sheet')

        cls.report_no_parent_id = cls.env["account.report"].create({
            'name': "Test report",

            'column_ids': [
                Command.create({
                    'name': 'Balance',
                    'expression_label': 'balance',
                    'sequence': 1
                })
            ],

            'line_ids': [
                Command.create({
                    'name': "Invisible Partner A line",
                    'code': "INVA",
                    'sequence': 1,
                    'hierarchy_level': 0,
                    'groupby': "account_id",
                    'foldability': 'foldable',
                    'expression_ids': [Command.clear(), Command.create({
                        'label': 'balance',
                        'engine': 'domain',
                        'formula': [("partner_id", "=", cls.partner_a.id)],
                        'subformula': 'sum',
                    })],
                }),
                Command.create({
                    'name': "Invisible Partner B line",
                    'code': "INVB",
                    'sequence': 2,
                    'hierarchy_level': 0,
                    'groupby': "account_id",
                    'foldability': 'foldable',
                    'expression_ids': [Command.clear(), Command.create({
                        'label': 'balance',
                        'engine': 'domain',
                        'formula': [("partner_id", "=", cls.partner_b.id)],
                        'subformula': 'sum',
                    })],
                }),
                Command.create({
                    'name': "Total of Invisible lines",
                    'code': "INVT",
                    'sequence': 3,
                    'hierarchy_level': 0,
                    'expression_ids': [Command.clear(), Command.create({
                        'label': 'balance',
                        'engine': 'aggregation',
                        'formula': 'INVA.balance + INVB.balance',
                    })],
                }),
            ],
        })

    def _build_generic_id_from_financial_line(self, financial_rep_ln_xmlid):
        report_line = self.env.ref(financial_rep_ln_xmlid)
        return '-account.financial.html.report.line-%s' % report_line.id

    def _get_line_id_from_generic_id(self, generic_id):
        return int(generic_id.split('-')[-1])

    def _press_journal_filter(self, options, journals):
        for option_journal in options['journals']:
            if option_journal.get('id') in journals.ids:
                option_journal['selected'] = not option_journal['selected']

    def test_financial_report_strict_range_on_report_lines_with_no_parent_id(self):
        """ Tests that lines with no parent can be correctly filtered by date range """
        options = self._generate_options(self.report_no_parent_id, '2019-01-01', '2019-12-31')

        lines = self.report_no_parent_id._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                         Balance
            [   0,                           1],
            [
                ('Invisible Partner A line', 1150.0),
                ('Invisible Partner B line', -1675.0),
                ('Total of Invisible lines', -525.0),

            ],
            options,
        )

    def test_financial_report_strict_empty_range_on_report_lines_with_no_parent_id(self):
        """ Tests that lines with no parent can be correctly filtered by date range with no invoices"""
        options = self._generate_options(self.report_no_parent_id, fields.Date.from_string('2019-03-01'), fields.Date.from_string('2019-03-31'))

        lines = self.report_no_parent_id._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                          Balance
            [   0,                            1],
            [
                ('Invisible Partner A line',  0.0),
                ('Invisible Partner B line',  0.0),
                ('Total of Invisible lines',  0.0),
            ],
            options,
        )

    @freeze_time("2016-06-06")
    def test_balance_sheet_today_current_year_earnings(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'date': '2016-02-02',
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'price_unit': 110,
                'tax_ids': [],
            })]
        })
        invoice.action_post()

        options = self._generate_options(self.report, '2016-06-01', '2016-06-06')
        options['date']['default_opening_date'] = 'today'

        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                            Balance
            [   0,                                              1],
            [
                ('ASSETS',                                      110.0),
                ('Current Assets',                              110.0),
                ('Bank and Cash Accounts',                        0.0),
                ('Receivables',                                 110.0),
                ('Current Assets',                                0.0),
                ('Prepayments',                                   0.0),
                ('Total Current Assets',                        110.0),
                ('Fixed Assets',                             0.0),
                ('Non-current Assets',                       0.0),
                ('Total ASSETS',                                110.0),

                ('LIABILITIES',                                   0.0),
                ('Current Liabilities',                           0.0),
                ('Current Liabilities',                           0.0),
                ('Credit Card',                                   0.0),
                ('Payables',                                      0.0),
                ('Total Current Liabilities',                     0.0),
                ('Non-current Liabilities',                  0.0),
                ('Total LIABILITIES',                             0.0),

                ('EQUITY (& EARNINGS)',                         110.0),
                ('Equity',                                        0.0),
                ('Earnings',                                    110.0),
                ('Current Year Unallocated Earnings',           110.0),
                ('Previous Years Earnings',                       0.0),
                ('Total Earnings',                              110.0),
                ('Total EQUITY (& EARNINGS)',                   110.0),

                ('LIABILITIES + EQUITY',                        110.0),
            ],
            options,
        )

    @freeze_time("2016-05-05")
    def test_balance_sheet_last_month_vs_custom_current_year_earnings(self):
        """
        Checks the balance sheet calls the right period of the P&L when using last_month date filter, or an equivalent custom filter
        (this used to fail due to options regeneration made by the P&L's get_options())"
        """
        to_invoice = [('15', '11'), ('15', '12'), ('16', '01'), ('16', '02'), ('16', '03'), ('16', '04')]
        for year, month in to_invoice:
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': f'20{year}-{month}-01',
                'invoice_line_ids': [Command.create({
                    'product_id': self.product_a.id,
                    'price_unit': 1000,
                    'tax_ids': [],
                })]
            })
            invoice.action_post()
        expected_result =[
                ('ASSETS',                                      6000.0),
                ('Current Assets',                              6000.0),
                ('Bank and Cash Accounts',                         0.0),
                ('Receivables',                                 6000.0),
                ('Current Assets',                                 0.0),
                ('Prepayments',                                    0.0),
                ('Total Current Assets',                        6000.0),
                ('Fixed Assets',                              0.0),
                ('Non-current Assets',                        0.0),
                ('Total ASSETS',                                6000.0),

                ('LIABILITIES',                                    0.0),
                ('Current Liabilities',                            0.0),
                ('Current Liabilities',                            0.0),
                ('Credit Card',                                    0.0),
                ('Payables',                                       0.0),
                ('Total Current Liabilities',                      0.0),
                ('Non-current Liabilities',                   0.0),
                ('Total LIABILITIES',                              0.0),

                ('EQUITY (& EARNINGS)',                         6000.0),
                ('Equity',                                         0.0),
                ('Earnings',                                    6000.0),
                ('Current Year Unallocated Earnings',           4000.0),
                ('Previous Years Earnings',                     2000.0),
                ('Total Earnings',                              6000.0),
                ('Total EQUITY (& EARNINGS)',                   6000.0),
                ('LIABILITIES + EQUITY',                        6000.0),

            ]
        options = self._generate_options(self.report, '2016-05-05', '2016-05-05')

        # End of Last Month
        options['date']['default_opening_date'] = 'last_month'
        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                            Balance
            [   0,                                              1],
            expected_result,
            options,
        )
        # Custom
        options['date']['period_type'] = 'custom'
        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                            Balance
            [   0,                                              1],
            expected_result,
            options,
        )

    def test_financial_report_single_company(self):
        self.env.companies = self.env.company

        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_bank_view0')
        options = self._generate_options(self.report, '2019-01-01', '2019-12-31')
        options['unfolded_lines'] = [line_id]

        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                            Balance
            [   0,                                              1],
            [
                ('ASSETS',                                        50.0),
                ('Current Assets',                              -650.0),
                ('Bank and Cash Accounts',                     -1300.0),
                ('code2 account2',                             -1300.0),
                ('Total Bank and Cash Accounts',               -1300.0),
                ('Receivables',                                 1350.0),
                ('Current Assets',                               400.0),
                ('Prepayments',                                -1100.0),
                ('Total Current Assets',                        -650.0),
                ('Fixed Assets',                              0.0),
                ('Non-current Assets',                      700.0),
                ('Total ASSETS',                                  50.0),

                ('LIABILITIES',                                 -200.0),
                ('Current Liabilities',                         -200.0),
                ('Current Liabilities',                            0.0),
                ('Credit Card',                                    0.0),
                ('Payables',                                    -200.0),
                ('Total Current Liabilities',                   -200.0),
                ('Non-current Liabilities',                   0.0),
                ('Total LIABILITIES',                           -200.0),

                ('EQUITY (& EARNINGS)',                          250.0),
                ('Equity',                                       800.0),
                ('Earnings',                                    -550.0),
                ('Current Year Unallocated Earnings',           -800.0),
                ('Previous Years Earnings',                      250.0),
                ('Total Earnings',                              -550.0),
                ('Total EQUITY (& EARNINGS)',                    250.0),

                ('LIABILITIES + EQUITY',                          50.0),
            ],
            options,
        )

        unfolded_lines = self.report._get_unfolded_lines(lines, line_id)
        self.assertLinesValues(
            unfolded_lines,
            #   Name                                            Balance
            [   0,                                              1],
            [
                ('Bank and Cash Accounts',                      -1300.0),
                ('code2 account2',                              -1300.0),
                ('Total Bank and Cash Accounts',                -1300.0),
            ],
            options,
        )

    def test_financial_report_multi_company_currency(self):
        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_bank_view0')
        options = self._generate_options(self.report, '2019-01-01', '2019-12-31')
        options['unfolded_lines'] = [line_id]

        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                            Balance
            [   0,                                              1],
            [
                ('ASSETS',                                        50.0),
                ('Current Assets',                             -4150.0),
                ('Bank and Cash Accounts',                     -3300.0),
                ('code102 account102',                         -2000.0),
                ('code2 account2',                             -1300.0),
                ('Total Bank and Cash Accounts',               -3300.0),
                ('Receivables',                                 2350.0),
                ('Current Assets',                               400.0),
                ('Prepayments',                                -3600.0),
                ('Total Current Assets',                       -4150.0),
                ('Fixed Assets',                              0.0),
                ('Non-current Assets',                     4200.0),
                ('Total ASSETS',                                  50.0),

                ('LIABILITIES',                                 -200.0),
                ('Current Liabilities',                         -200.0),
                ('Current Liabilities',                            0.0),
                ('Credit Card',                                    0.0),
                ('Payables',                                    -200.0),
                ('Total Current Liabilities',                   -200.0),
                ('Non-current Liabilities',                   0.0),
                ('Total LIABILITIES',                           -200.0),

                ('EQUITY (& EARNINGS)',                          250.0),
                ('Equity',                                       800.0),
                ('Earnings',                                    -550.0),
                ('Current Year Unallocated Earnings',           -800.0),
                ('Previous Years Earnings',                      250.0),
                ('Total Earnings',                              -550.0),
                ('Total EQUITY (& EARNINGS)',                    250.0),

                ('LIABILITIES + EQUITY',                          50.0),
            ],
            options,
        )

        unfolded_lines = self.report._get_unfolded_lines(lines, line_id)
        self.assertLinesValues(
            unfolded_lines,
            #   Name                                            Balance
            [   0,                                              1],
            [
                ('Bank and Cash Accounts',                     -3300.0),
                ('code102 account102',                         -2000.0),
                ('code2 account2',                             -1300.0),
                ('Total Bank and Cash Accounts',               -3300.0),
            ],
            options,
        )

    def test_financial_report_comparison(self):
        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_bank_view0')
        options = self._generate_options(self.report, '2019-01-01', '2019-12-31')

        for period_order in ('descending', 'ascending'):
            options = self._update_comparison_filter(options, self.report, 'custom', 1, date_to=fields.Date.from_string('2018-12-31'), period_order=period_order)
            options['unfolded_lines'] = [line_id]

            lines = self.report._get_lines(options)
            self.assertColumnPercentComparisonValues(
                lines,
                [
                    ('ASSETS',                                      '-80.0%',       'red'),
                    ('Current Assets',                              '27.7%',        'red'),
                    ('Bank and Cash Accounts',                      '10.0%',        'red'),
                    ('code102 account102',                          '0.0%',       'muted'),
                    ('code2 account2',                              '30.0%',        'red'),
                    ('Total Bank and Cash Accounts',                '10.0%',        'red'),
                    ('Receivables',                                 '4.4%',       'green'),
                    ('Current Assets',                              'n/a',        'muted'),
                    ('Prepayments',                                 '44.0%',        'red'),
                    ('Total Current Assets',                        '27.7%',        'red'),
                    ('Fixed Assets',                           'n/a',        'muted'),
                    ('Non-current Assets',                     '20.0%',      'green'),
                    ('Total ASSETS',                                '-80.0%',       'red'),

                    ('LIABILITIES',                                 'n/a',        'muted'),
                    ('Current Liabilities',                         'n/a',        'muted'),
                    ('Current Liabilities',                         'n/a',        'muted'),
                    ('Credit Card',                                 'n/a',        'muted'),
                    ('Payables',                                    'n/a',        'muted'),
                    ('Total Current Liabilities',                   'n/a',        'muted'),
                    ('Non-current Liabilities',                'n/a',        'muted'),
                    ('Total LIABILITIES',                           'n/a',        'muted'),

                    ('EQUITY (& EARNINGS)',                         '0.0%',       'muted'),
                    ('Equity',                                       'n/a',       'muted'),
                    ('Earnings',                                    '-320.0%',      'red'),
                    ('Current Year Unallocated Earnings',           '-420.0%',      'red'),
                    ('Previous Years Earnings',                     'n/a',        'muted'),
                    ('Total Earnings',                              '-320.0%',      'red'),
                    ('Total EQUITY (& EARNINGS)',                   '0.0%',       'muted'),

                    ('LIABILITIES + EQUITY',                        '-80.0%',     'green'),
                ]
            )

    def test_financial_report_comparison_amount_column(self):
        """ growth_display='amount' shows the monetary delta in the comparison column, formatted against
        the active rounding_unit option. """
        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_bank_view0')
        options = self._generate_options(
            self.report, '2019-01-01', '2019-12-31',
            default_options={'growth_display': 'amount'},
        )
        options = self._update_comparison_filter(options, self.report, 'custom', 1, date_to=fields.Date.from_string('2018-12-31'))
        options['unfolded_lines'] = [line_id]

        lines = self.report._get_lines(options)
        self.assertColumnAmountComparisonValues(
            lines,
            [
                ('ASSETS',                              -200.0,     'red'),
                ('Current Assets',                      -900.0,     'red'),
                ('Bank and Cash Accounts',              -300.0,     'red'),
                ('code102 account102',                     0.0,   'muted'),
                ('code2 account2',                      -300.0,     'red'),
                ('Total Bank and Cash Accounts',        -300.0,     'red'),
                ('Receivables',                          100.0,   'green'),
                ('Current Assets',                       400.0,   'green'),
                ('Prepayments',                        -1100.0,     'red'),
                ('Total Current Assets',                -900.0,     'red'),
                ('Fixed Assets',                             0,   'muted'),
                ('Non-current Assets',                   700.0,   'green'),
                ('Total ASSETS',                        -200.0,     'red'),
                ('LIABILITIES',                         -200.0,   'green'),
                ('Current Liabilities',                 -200.0,   'green'),
                ('Current Liabilities',                      0,   'muted'),
                ('Credit Card',                              0,   'muted'),
                ('Payables',                            -200.0,   'green'),
                ('Total Current Liabilities',           -200.0,   'green'),
                ('Non-current Liabilities',                  0,   'muted'),
                ('Total LIABILITIES',                   -200.0,   'green'),
                ('EQUITY (& EARNINGS)',                    0.0,   'muted'),
                ('Equity',                               800.0,   'green'),
                ('Earnings',                            -800.0,     'red'),
                ('Current Year Unallocated Earnings',  -1050.0,     'red'),
                ('Previous Years Earnings',              250.0,   'green'),
                ('Total Earnings',                      -800.0,     'red'),
                ('Total EQUITY (& EARNINGS)',              0.0,   'muted'),
                ('LIABILITIES + EQUITY',                -200.0,   'green'),
            ],
        )

    def test_financial_report_comparison_amount_rounding_unit(self):
        """ Switching the rounding_unit must reformat the rendered name while leaving the underlying delta intact. """
        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_bank_view0')
        options = self._generate_options(
            self.report, '2019-01-01', '2019-12-31',
            default_options={'growth_display': 'amount'},
        )
        options = self._update_comparison_filter(options, self.report, 'custom', 1, date_to=fields.Date.from_string('2018-12-31'))
        options['unfolded_lines'] = [line_id]

        lines = self.report._get_lines(options)
        options['rounding_unit'] = 'thousands'
        thousands_lines = self.report._get_lines(options)
        for original, scaled in zip(lines, thousands_lines):
            self.assertEqual(original.column_percent_comparison_data.no_format, scaled.column_percent_comparison_data.no_format)
            if original.column_percent_comparison_data.no_format and abs(original.column_percent_comparison_data.no_format) >= 1000:
                self.assertNotEqual(original.column_percent_comparison_data.name, scaled.column_percent_comparison_data.name)

    def test_financial_report_line_comparison(self):
        self._create_test_account_moves([
            self._prepare_test_account_move_line(1000.0, account_code='100000', date='2010-01-01'),
            self._prepare_test_account_move_line(10.0, account_code='200000', date='2010-01-01'),
            self._prepare_test_account_move_line(200.0, account_code='300000', date='2010-01-01'),
            self._prepare_test_account_move_line(2000.0, account_code='500001', date='2010-01-01'),
        ])

        report = self._create_report([
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('1')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('2')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('3')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('4')),
            self._prepare_test_report_line(self._prepare_test_expression_account_codes('5')),
            self._prepare_test_report_line(),
        ], filter_line_comparison=True)

        options = self._generate_options(
            report,
            '2010-01-01',
            '2010-01-01',
            default_options={'comparison': {'filter': 'report_line', 'base_report_line': {'id': report.line_ids[0].id, 'name': report.line_ids[0].name}, 'name': report.line_ids[0].name}},
        )

        lines = report._get_lines(options)
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            lines,
            [   0,                          1],
            [
                ('test_line_1',        1000.0),
                ('test_line_2',          10.0),
                ('test_line_3',         200.0),
                ('test_line_4',           0.0),
                ('test_line_5',        2000.0),
                ('test_line_6',            ''),
            ],
            options,
        )

        self.assertColumnPercentComparisonValues(
            # pylint: disable=bad-whitespace
            lines,
            [
                ('test_line_1',      '100.0%',         ''),
                ('test_line_2',        '1.0%',      'red'),
                ('test_line_3',       '20.0%',      'red'),
                ('test_line_4',        '0.0%',      'red'),
                ('test_line_5',      '200.0%',      'green'),
                ('test_line_6',         'n/a',      'muted'),
            ],
        )

        zero_comparison_options = self._generate_options(
            report,
            '2010-01-01',
            '2010-01-01',
            default_options={'comparison': {'filter': 'report_line', 'base_report_line': {'id': report.line_ids[3].id, 'name': report.line_ids[3].name}, 'name': report.line_ids[3].name}},
        )

        self.assertColumnPercentComparisonValues(
            # pylint: disable=bad-whitespace
            report._get_lines(zero_comparison_options),
            [
                ('test_line_1',         'n/a',      'muted'),
                ('test_line_2',         'n/a',      'muted'),
                ('test_line_3',         'n/a',      'muted'),
                ('test_line_4',         'n/a',      'muted'),
                ('test_line_5',         'n/a',      'muted'),
                ('test_line_6',         'n/a',      'muted'),
            ],
        )

    def test_financial_report_horizontal_group(self):
        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_receivable0')
        self.report.horizontal_group_ids |= self.horizontal_group

        options = self._generate_options(
            self.report,
            fields.Date.from_string('2019-01-01'),
            fields.Date.from_string('2019-12-31'),
            default_options={
                'unfolded_lines': [line_id],
                'selected_horizontal_group_id': self.horizontal_group.id,
            }
        )
        options = self._update_comparison_filter(options, self.report, 'custom', 1, date_to=fields.Date.from_string('2018-12-31'))
        lines = self.report._get_lines(options)
        self.assertHeadersValues(
            options['column_headers'],
            [
                ['As of 12/31/2019', 'As of 12/31/2018'],
                ['partner_a', 'partner_b'],
                ['code0 account0', 'code1 account1'],
            ]
        )
        self.assertLinesValues(
            lines,
            [   0,                                          1,                   2,                  3,                  4,                  5,                  6,                  7,                  8],
            [
                ('ASSETS',                                  1300.0,             0.0,                 25.0,              0.0,                 1250.0,            0.0,                0.0,                0.0),
                ('Current Assets',                          1300.0,             0.0,                 25.0,              0.0,                 1250.0,            0.0,                0.0,                0.0),
                ('Bank and Cash Accounts',                 0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Receivables',                             1300.0,             0.0,                 25.0,              0.0,                 1250.0,            0.0,                0.0,                0.0),
                ('code0 account0',                          1300.0,             0.0,                 25.0,              0.0,                 1250.0,            0.0,                0.0,                0.0),
                ('Total Receivables',                       1300.0,             0.0,                 25.0,              0.0,                 1250.0,            0.0,                0.0,                0.0),
                ('Current Assets',                         0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Prepayments',                            0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Total Current Assets',                    1300.0,             0.0,                 25.0,              0.0,                 1250.0,            0.0,                0.0,                0.0),
                ('Fixed Assets',                      0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Non-current Assets',                0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Total ASSETS',                            1300.0,             0.0,                 25.0,              0.0,                 1250.0,            0.0,                0.0,                0.0),

                ('LIABILITIES',                            0.0,                 0.0,                0.0,                -200.0,             0.0,                0.0,                0.0,                0.0),
                ('Current Liabilities',                    0.0,                 0.0,                0.0,                -200.0,             0.0,                0.0,                0.0,                0.0),
                ('Current Liabilities',                    0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Credit Card',                            0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Payables',                               0.0,                 0.0,                0.0,                -200.0,             0.0,                0.0,                0.0,                0.0),
                ('Total Current Liabilities',              0.0,                 0.0,                0.0,                -200.0,             0.0,                0.0,                0.0,                0.0),
                ('Non-current Liabilities',           0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Total LIABILITIES',                      0.0,                 0.0,                0.0,                -200.0,             0.0,                0.0,                0.0,                0.0),

                ('EQUITY (& EARNINGS)',                    0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Equity',                                 0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Earnings',                               0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Current Year Unallocated Earnings',      0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Previous Years Earnings',                0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Total Earnings',                         0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),
                ('Total EQUITY (& EARNINGS)',              0.0,                 0.0,                0.0,                0.0,                0.0,                0.0,                0.0,                0.0),

                ('LIABILITIES + EQUITY',                   0.0,                 0.0,                0.0,                -200.0,             0.0,                0.0,                0.0,                0.0),
            ],
            options,
        )

    def test_financial_report_horizontal_group_total(self):
        """
        In case we don't have comparison, just one column and one level of groupby a new column is added which is the total
        of the horizontal group
        """
        horizontal_group = self.env['account.report.horizontal.group'].create({
            'name': 'Horizontal Group total',
            'rule_ids': [
                Command.create({
                    'field_name': 'partner_id',
                    'domain': f"[('id', 'in', {(self.partner_a + self.partner_b).ids})]",
                }),
            ],
        })
        self.report.horizontal_group_ids |= horizontal_group
        options = self._generate_options(self.report, '2019-01-01', '2019-12-31', default_options={'selected_horizontal_group_id': horizontal_group.id})
        self.assertHeadersValues(
            options['column_headers'],
            [
                ['As of 12/31/2019'],
                ['partner_a', 'partner_b'],
            ]
        )

        self.assertTrue(options['show_horizontal_group_total'])
        # Since we don't calculate the value when totals below section is activated, we disable it
        self.env.company.totals_below_sections = False
        self.assertHorizontalGroupTotal(
            self.report._get_lines(options),
            [
                ('ASSETS',                                      6900.0,          -4075.0,        2825.0),
                ('Current Assets',                              2700.0,          -4075.0,       -1375.0),
                ('Bank and Cash Accounts',                         0.0,          -3000.0,       -3000.0),
                ('Receivables',                                 2300.0,             25.0,        2325.0),
                ('Current Assets',                               400.0,              0.0,         400.0),
                ('Prepayments',                                    0.0,          -1100.0,       -1100.0),
                ('Fixed Assets',                              0.0,              0.0,           0.0),
                ('Non-current Assets',                     4200.0,              0.0,        4200.0),
                ('LIABILITIES',                                    0.0,           -200.0,        -200.0),
                ('Current Liabilities',                            0.0,           -200.0,        -200.0),
                ('Current Liabilities',                            0.0,              0.0,           0.0),
                ('Credit Card',                                    0.0,              0.0,           0.0),
                ('Payables',                                       0.0,           -200.0,        -200.0),
                ('Non-current Liabilities',                   0.0,              0.0,           0.0),
                ('EQUITY (& EARNINGS)',                          250.0,            800.0,        1050.0),
                ('Equity',                                         0.0,            800.0,         800.0),
                ('Earnings',                                     250.0,              0.0,         250.0),
                ('Current Year Unallocated Earnings',              0.0,              0.0,           0.0),
                ('Previous Years Earnings',                      250.0,              0.0,         250.0),
                ('LIABILITIES + EQUITY',                         250.0,            600.0,         850.0),
            ],
        )

        options = self._generate_options(self.report, '2019-01-01', '2019-12-31', default_options={'selected_horizontal_group_id': horizontal_group.id})
        options = self._update_comparison_filter(options, self.report, 'custom', 1, date_to=fields.Date.from_string('2018-12-31'))
        self.assertHeadersValues(
            options['column_headers'],
            [
                ['As of 12/31/2019', 'As of 12/31/2018'],
                ['partner_a', 'partner_b'],
            ]
        )

        self.assertFalse(options['show_horizontal_group_total'])

        self.assertHorizontalGroupTotal(
            self.report._get_lines(options),
            [
                ('ASSETS',                                      6900.0,             -4075.0,     5750.0,     -3000.0),
                ('Current Assets',                              2700.0,             -4075.0,     2250.0,     -3000.0),
                ('Bank and Cash Accounts',                         0.0,             -3000.0,        0.0,     -3000.0),
                ('Receivables',                                 2300.0,                25.0,     2250.0,         0.0),
                ('Current Assets',                               400.0,                 0.0,        0.0,         0.0),
                ('Prepayments',                                    0.0,             -1100.0,        0.0,         0.0),
                ('Fixed Assets',                              0.0,                 0.0,        0.0,         0.0),
                ('Non-current Assets',                     4200.0,                 0.0,     3500.0,         0.0),
                ('LIABILITIES',                                    0.0,              -200.0,        0.0,         0.0),
                ('Current Liabilities',                            0.0,              -200.0,        0.0,         0.0),
                ('Current Liabilities',                            0.0,                 0.0,        0.0,         0.0),
                ('Credit Card',                                    0.0,                 0.0,        0.0,         0.0),
                ('Payables',                                       0.0,              -200.0,        0.0,         0.0),
                ('Non-current Liabilities',                   0.0,                 0.0,        0.0,         0.0),
                ('EQUITY (& EARNINGS)',                          250.0,               800.0,      250.0,         0.0),
                ('Equity',                                         0.0,               800.0,        0.0,         0.0),
                ('Earnings',                                     250.0,                 0.0,      250.0,         0.0),
                ('Current Year Unallocated Earnings',              0.0,                 0.0,      250.0,         0.0),
                ('Previous Years Earnings',                      250.0,                 0.0,        0.0,         0.0),
                ('LIABILITIES + EQUITY',                         250.0,               600.0,      250.0,         0.0),
            ],
        )

    def test_show_horizontal_group_ledger(self):
        """
        The default horizontal group 'Ledger' should be displayed only when relevant, i.e
            * If at least 2 companies are running, or
            * If at least one ledger exists and one journal of the running company is included in a ledger
        """
        horizontal_group_ledger = self.env.ref('account_reports.horizontal_group_ledger')

        # 1. No existing ledger but 2 running companies
        options = self._generate_options(self.report, '2019-01-01', '2019-12-31')
        self.assertDictEqual(options['available_horizontal_groups'][0], {
            'id': horizontal_group_ledger.id,
            'name': horizontal_group_ledger.name,
        })

        # 2. Switching to only company_data_2
        env = self.env(context={
            **self.env.context,
            'allowed_company_ids': [self.company_data_2['company'].id],
            'company_id': self.company_data_2['company'].id,
        })
        options = self._generate_options(self.report.with_env(env), '2019-01-01', '2019-12-31')
        self.assertEqual(options['available_horizontal_groups'], [])

        # 2. Creating a ledger including a journal from company_data_2
        self.env['account.journal.group'].create({
            'name': 'MISC',
            'included_journal_ids': self.company_data_2['default_journal_misc'],
        })

        options = self._generate_options(self.report, '2019-01-01', '2019-12-31')
        self.assertDictEqual(options['available_horizontal_groups'][0], {
            'id': horizontal_group_ledger.id,
            'name': horizontal_group_ledger.name,
        })

    def test_hide_if_zero_with_no_formulas(self):
        """
        Check if a report line stays displayed when hide_if_zero is True and no formulas
        is set on the line but has some child which have balance != 0
        We check also if the line is hidden when all its children have balance == 0
        """
        account1, account2 = self.env['account.account'].create([{
            'name': "test_financial_report_1",
            'code': "42241",
            'account_type': "asset_fixed",
        }, {
            'name': "test_financial_report_2",
            'code': "42242",
            'account_type': "asset_fixed",
        }])

        moves = self.env['account.move'].create([
            {
                'move_type': 'entry',
                'date': '2019-04-01',
                'line_ids': [
                    (0, 0, {'debit': 3.0, 'credit': 0.0, 'account_id': account1.id}),
                    (0, 0, {'debit': 0.0, 'credit': 3.0, 'account_id': self.company_data['default_account_revenue'].id}),
                ],
            },
            {
                'move_type': 'entry',
                'date': '2019-05-01',
                'line_ids': [
                    (0, 0, {'debit': 0.0, 'credit': 1.0, 'account_id': account2.id}),
                    (0, 0, {'debit': 1.0, 'credit': 0.0, 'account_id': self.company_data['default_account_revenue'].id}),
                ],
            },
            {
                'move_type': 'entry',
                'date': '2019-04-01',
                'line_ids': [
                    (0, 0, {'debit': 0.0, 'credit': 3.0, 'account_id': account2.id}),
                    (0, 0, {'debit': 3.0, 'credit': 0.0, 'account_id': self.company_data['default_account_revenue'].id}),
                ],
            },
        ])
        moves.action_post()
        moves.line_ids.flush_recordset()

        report = self.env["account.report"].create({
            'name': "test_financial_report_sum",
            'column_ids': [
                Command.create({
                    'name': "Balance",
                    'expression_label': 'balance',
                    'sequence': 1,
                }),
            ],
            'line_ids': [
                Command.create({
                    'name': "Title",
                    'code': 'TT',
                    'hide_if_zero': True,
                    'sequence': 0,
                    'children_ids': [
                        Command.create({
                            'name': "report_line_1",
                            'code': 'TEST_L1',
                            'sequence': 1,
                            'expression_ids': [
                                Command.create({
                                    'label': 'balance',
                                    'engine': 'domain',
                                    'formula': f"[('account_id', '=', {account1.id})]",
                                    'subformula': 'sum',
                                    'date_scope': 'from_beginning',
                                }),
                            ],
                        }),
                        Command.create({
                            'name': "report_line_2",
                            'code': 'TEST_L2',
                            'sequence': 2,
                            'expression_ids': [
                                Command.create({
                                    'label': 'balance',
                                    'engine': 'domain',
                                    'formula': f"[('account_id', '=', {account2.id})]",
                                    'subformula': 'sum',
                                    'date_scope': 'from_beginning',
                                }),
                            ],
                        }),
                    ]
                }),
            ],
        })

        # TODO without this, the create() puts newIds in the sublines, and flushing doesn't help. Seems to be an ORM bug.
        self.env.invalidate_all()

        options = self._generate_options(report, '2019-05-01', '2019-05-31')
        options = self._update_comparison_filter(options, report, 'previous_period', 2)

        self.assertLinesValues(
            report._get_lines(options),
            [   0,                                   1,       2,       3],
            [
                ("Title",                           '',      '',      ''),
                ("report_line_1",                  3.0,     3.0,     0.0),
                ("report_line_2",                 -4.0,    -3.0,     0.0),
            ],
            options,
        )

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2019-05-01',
            'line_ids': [
                (0, 0, {'debit': 0.0, 'credit': 3.0, 'account_id': account1.id}),
                (0, 0, {'debit': 4.0, 'credit': 0.0, 'account_id': account2.id}),
                (0, 0, {'debit': 0.0, 'credit': 1.0, 'account_id': self.company_data['default_account_revenue'].id}),
            ],
        })

        move.action_post()
        move.line_ids.flush_recordset()

        # With the comparison still on, the lines shouldn't be hidden
        self.assertLinesValues(
            report._get_lines(options),
            [   0,                                   1,       2,       3],
            [
                ("Title",                           '',      '',      ''),
                ("report_line_1",                  0.0,     3.0,     0.0),
                ("report_line_2",                  0.0,    -3.0,     0.0),
            ],
            options,
        )

        # Removing the comparison should hide the lines, as they will be 0 in every considered period (the current one)
        options = self._update_comparison_filter(options, report, 'previous_period', 0)
        self.assertLinesValues(report._get_lines(options), [0, 1, 2, 3], [], options)

    def test_option_hierarchy(self):
        """ Check that the report lines are correct when the option "Hierarchy and subtotals is ticked"""
        self.company_data['default_account_revenue'].parent_id = self.env['account.account'].create({
            'code': '40.49',
            'name': 'Sales',
            'account_type': 'income',
            'active': False,
        })

        move = self.env['account.move'].create({
            'date': '2020-02-02',
            'line_ids': [
                Command.create({
                    'account_id': self.company_data['default_account_revenue'].id,
                    'name': 'name',
                })
            ],
        })
        move.action_post()
        move.line_ids.flush_recordset()
        profit_and_loss_report = self.env.ref('account_reports.profit_and_loss')
        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_revenue0')
        options = self._generate_options(profit_and_loss_report, '2020-02-01', '2020-02-28')
        options['unfolded_lines'] = [line_id]
        options['hierarchy'] = True
        self.env.company.totals_below_sections = False
        lines = profit_and_loss_report._get_lines(options)

        unfolded_lines = profit_and_loss_report._get_unfolded_lines(lines, line_id)
        unfolded_lines = [{'name': line.name, 'level': line.level} for line in unfolded_lines]

        self.assertEqual(
            unfolded_lines,
            [
                {'level': 1, 'name': 'Revenue'},
                {'level': 2, 'name': '40.49 Sales'},
                {'level': 3, 'name': '400000 Product Sales'},
            ]
        )

    def test_option_hierarchy_with_no_group_lines(self):
        """ Check that the report lines with no parent are correct with the option 'Hierarchy and subtotals' """
        self.env['account.account'].create({
            'code': '45.49',
            'name': 'Sales',
            'account_type': 'income',
            'active': False,
        })

        move = self.env['account.move'].create({
            'date': '2020-02-02',
            'line_ids': [
                Command.create({
                    'account_id': self.company_data['default_account_revenue'].id,
                    'name': 'name',
                })
            ],
        })
        move.action_post()
        move.line_ids.flush_recordset()
        profit_and_loss_report = self.env.ref('account_reports.profit_and_loss')
        line_id = self._get_basic_line_dict_id_from_report_line_ref('account_reports.account_financial_report_revenue0')
        options = self._generate_options(profit_and_loss_report, '2020-02-01', '2020-02-28')
        options['unfolded_lines'] = [line_id]
        options['hierarchy'] = True
        self.env.company.totals_below_sections = False
        lines = profit_and_loss_report._get_lines(options)
        lines_array = [{'name': line.name, 'level': line.level} for line in lines]

        self.assertEqual(
            lines_array,
            [
                {'name': 'Revenue', 'level': 1},
                {'name': '400000 Product Sales', 'level': 2},
                {'name': 'Costs of Revenue', 'level': 1},
                {'name': 'Gross Profit', 'level': 0},
                {'name': 'Operating Expenses', 'level': 1},
                {'name': 'Operating Income (or Loss)', 'level': 0},
                {'name': 'Other Income', 'level': 1},
                {'name': 'Other Expenses', 'level': 1},
                {'name': 'Net Profit', 'level': 0},
                {'name': 'Allocations and Withdrawals', 'level': 1},
            ]
        )

    def test_parse_line_id(self):
        line_id_1 = self.env['account.report']._parse_line_id('markup1~account.account~5|markup2~res.partner~8|markup3~~')
        line_id_2 = self.env['account.report']._parse_line_id('~account.report~14|{"groupby_prefix_group": "~"}~account.report~21')

        self.assertEqual(line_id_1, [('markup1', 'account.account', 5), ('markup2', 'res.partner', 8), ('markup3', None, None)])
        self.assertEqual(line_id_2, [('', 'account.report', 14), ({"groupby_prefix_group": "~"}, 'account.report', 21)])

    def test_multi_ledger_horizontal_group(self):
        def _create_journal_group(name, included_journal_ids, company):
            return self.env['account.journal.group'].create({
                'name': name,
                'included_journal_ids': [Command.set(included_journal_ids)],
            })
        c1 = self.company_data['company']
        c2 = self.company_data_2['company']
        context = dict(self.env.context, allowed_company_ids=[c1.id, c2.id])
        self.env = self.env(context=context)

        c1_sale = self.company_data['default_journal_sale']
        c2_sale = self.company_data_2['default_journal_sale']
        c1_c2_journals_sale = self.env['account.journal'].search([
            ('company_id', 'in', [c1.id, c2.id]),
            ('id', 'in', [c1_sale.id, c2_sale.id])
        ])
        c1_c2_sale_ledger = _create_journal_group('Sale of C1, C2', c1_c2_journals_sale.ids, False)
        report = self.env.ref('account_reports.profit_and_loss')
        horizontal_group = self.env['account.report.horizontal.group'].create({
            'name': 'Multi-Ledger',
            'report_ids': [Command.set(report.ids)],
            'rule_ids': [
                Command.create({
                    'field_name': 'journal_group_id',
                    'domain':  str([('id', 'in', (c1_c2_sale_ledger).ids)]),
                }),
            ],
        })
        report.horizontal_group_ids |= horizontal_group

        c1_move_data = [
            {
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': fields.Date.from_string('2020-01-03'),
                'journal_id': c1_sale.id,
                'invoice_line_ids': [Command.create({'price_unit': 100.0, 'account_id': self.company_data['default_account_revenue'].id})],
            },
            {
                'move_type': 'in_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': fields.Date.from_string('2020-01-03'),
                'journal_id': self.company_data['default_journal_purchase'].id,
                'invoice_line_ids': [Command.create({'price_unit': 100.0, 'account_id': self.company_data['default_account_expense'].id})],
            },
        ]

        c1_moves = self.env['account.move'].with_company(c1).create(c1_move_data)
        c1_moves.action_post()

        # 1 USD = 2 CAD
        c2_move_data = [
            {
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': fields.Date.from_string('2020-01-03'),
                'journal_id': c2_sale.id,
                'invoice_line_ids': [Command.create({'price_unit': 100.0, 'account_id': self.company_data_2['default_account_revenue'].id})],
            },
            {
                'move_type': 'in_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': fields.Date.from_string('2020-01-03'),
                'journal_id': self.company_data_2['default_journal_purchase'].id,
                'invoice_line_ids': [Command.create({'price_unit': 100.0, 'account_id': self.company_data_2['default_account_expense'].id})],
            },
        ]
        c2_moves = self.env['account.move'].with_company(c2).create(c2_move_data)
        c2_moves.action_post()

        ledgers = c1_c2_sale_ledger + self.env['account.journal.group'].browse(['local_gaap'])
        options = self._generate_options(report, '2020-01-01', '2020-12-31', default_options={
            'selected_horizontal_group_id': horizontal_group.id,
            'journals': [{'id': j.id, 'selected': True} for j in ledgers.included_journal_ids],
        })

        self.assertLinesValues(
            report._get_lines(options),
            #       Name                                                    C1                   C2              Sale of C1, C2
            [0,                                                      1,                   2,                    3],
            [
                ('Revenue',                                                0.0,                 0.0,                150.0),
                ('Costs of Revenue',                                       0.0,                 0.0,                  0.0),
                ('Gross Profit',                                           0.0,                 0.0,                150.0),
                ('Operating Expenses',                                   100.0,                50.0,                  0.0),
                ('Operating Income (or Loss)',                          -100.0,               -50.0,                150.0),
                ('Other Income',                                           0.0,                 0.0,                  0.0),
                ('Other Expenses',                                         0.0,                 0.0,                  0.0),
                ('Net Profit',                                          -100.0,               -50.0,                150.0),
                ('Allocations and Withdrawals',                            0.0,                 0.0,                  0.0),
            ],
            options,
        )

        # If no journal group exists and we're in multicompany, the Ledger group should basically do a grouping per company.
        c1_c2_sale_ledger.unlink()
        horizontal_group_ledger = self.env.ref('account_reports.horizontal_group_ledger')
        options = self._generate_options(report, '2020-01-01', '2020-12-31', default_options={'selected_horizontal_group_id': horizontal_group_ledger.id})

        self.assertLinesValues(
            report._get_lines(options),
            #       Name                                                    C1                   C2
            [0,                                                              1,                   2],
            [
                ('Revenue',                                              100.0,                50.0),
                ('Costs of Revenue',                                       0.0,                 0.0),
                ('Gross Profit',                                         100.0,                50.0),
                ('Operating Expenses',                                   100.0,                50.0),
                ('Operating Income (or Loss)',                             0.0,                 0.0),
                ('Other Income',                                           0.0,                 0.0),
                ('Other Expenses',                                         0.0,                 0.0),
                ('Net Profit',                                             0.0,                 0.0),
                ('Allocations and Withdrawals',                            0.0,                 0.0),
            ],
            options,
        )

    def test_options_sanitization(self):
        """ Test that options including custom ranges are well-sanitized and can be serialized """
        report = self.env.ref('account_reports.general_ledger_report')

        for custom_range in [
            ('2024-02-14', '2024-12-31', 'FY 2024_2'),
            ('2025-01-01', '2025-04-30', 'FY 2025_1'),
            ('2025-05-01', '2025-12-31', 'FY 2025_2'),
            ('2026-05-01', '2026-06-30', 'FY 2026_2'),
        ]:
            self.env['account.fiscal.year'].create({
                'name': custom_range[2],
                'date_from': custom_range[0],
                'date_to': custom_range[1],
                'company_id': self.env.company.id,
            })

        options = report.get_options({'date': {'default_opening_date': 'this_year'}})
        json.dumps(options)
