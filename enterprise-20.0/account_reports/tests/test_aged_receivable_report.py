# -*- coding: utf-8 -*-
# pylint: disable=C0326
from .common import TestAccountReportsCommon

from odoo import fields, Command
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAgedReceivableReport(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_category_a = cls.env['res.partner.category'].create({'name': 'partner_categ_a'})
        cls.partner_category_b = cls.env['res.partner.category'].create({'name': 'partner_categ_b'})

        cls.partner_a.write({'category_id': [Command.set([cls.partner_category_a.id, cls.partner_category_b.id])]})
        cls.partner_b.write({'category_id': [Command.set([cls.partner_category_a.id])]})

        receivable_1 = cls.company_data['default_account_receivable']
        receivable_2 = cls.copy_account(cls.company_data['default_account_receivable'])
        receivable_3 = cls.copy_account(cls.company_data['default_account_receivable'])
        receivable_4 = cls.company_data_2['default_account_receivable']
        receivable_5 = cls.copy_account(cls.company_data_2['default_account_receivable'])
        receivable_6 = cls.copy_account(cls.company_data_2['default_account_receivable'])
        misc_1 = cls.company_data['default_account_revenue']
        misc_2 = cls.company_data_2['default_account_revenue']

        # Test will use the following dates:
        # As of                  2017-02-01
        # 1 - 30:   2017-01-31 - 2017-01-02
        # 31 - 60:  2017-01-01 - 2016-12-03
        # 61 - 90:  2016-12-02 - 2016-11-03
        # 91 - 120: 2016-11-02 - 2016-10-04
        # Older:    2016-10-03

        # ==== Journal entries in company_1 for partner_a ====

        move_1 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-11-03'),
            'invoice_date': fields.Date.from_string('2016-11-03'),
            'journal_id': cls.company_data['default_journal_sale'].id,
            'line_ids': [
                # 1000.0 in 61 - 90.
                Command.create({'debit': 1000.0,    'credit': 0.0,      'date_maturity': False,         'account_id': receivable_1.id,      'partner_id': cls.partner_a.id}),
                # -800.0 in 31 - 60
                Command.create({'debit': 0.0,       'credit': 800.0,    'date_maturity': '2017-01-01',  'account_id': receivable_2.id,      'partner_id': cls.partner_a.id}),
                # Ignored line.
                Command.create({'debit': 0.0,       'credit': 200.0,    'date_maturity': False,         'account_id': misc_1.id,            'partner_id': cls.partner_a.id}),
            ],
        })

        move_2 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-10-05'),
            'invoice_date': fields.Date.from_string('2016-10-05'),
            'journal_id': cls.company_data['default_journal_sale'].id,
            'line_ids': [
                # -200.0 in 61 - 90
                Command.create({'debit': 0.0,       'credit': 200.0,    'date_maturity': '2016-12-02',  'account_id': receivable_1.id,      'partner_id': cls.partner_a.id}),
                # -300.0 in 31 - 60
                Command.create({'debit': 0.0,       'credit': 300.0,    'date_maturity': '2016-12-03',  'account_id': receivable_1.id,      'partner_id': cls.partner_a.id}),
                # 1000.0 in 91 - 120
                Command.create({'debit': 1000.0,    'credit': 0.0,      'date_maturity': False,         'account_id': receivable_2.id,      'partner_id': cls.partner_a.id}),
                # 100.0 in all dates
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2017-02-01',  'account_id': receivable_3.id,      'partner_id': cls.partner_a.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2017-01-02',  'account_id': receivable_3.id,      'partner_id': cls.partner_a.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-12-03',  'account_id': receivable_3.id,      'partner_id': cls.partner_a.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-11-03',  'account_id': receivable_3.id,      'partner_id': cls.partner_a.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-10-04',  'account_id': receivable_3.id,      'partner_id': cls.partner_a.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-01-01',  'account_id': receivable_3.id,      'partner_id': cls.partner_a.id}),
                # Ignored line.
                Command.create({'debit': 0.0,       'credit': 1100.0,   'date_maturity': '2016-10-05',  'account_id': misc_1.id,            'partner_id': cls.partner_a.id}),
            ],
        })
        (move_1 + move_2).action_post()
        (move_1 + move_2).line_ids.filtered(lambda line: line.account_id == receivable_1).reconcile()
        (move_1 + move_2).line_ids.filtered(lambda line: line.account_id == receivable_2).reconcile()

        # ==== Journal entries in company_2 for partner_b ====

        move_3 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-11-03'),
            'invoice_date': fields.Date.from_string('2016-11-03'),
            'journal_id': cls.company_data_2['default_journal_sale'].id,
            'line_ids': [
                # 1000.0 in 61 - 90.
                Command.create({'debit': 1000.0,    'credit': 0.0,      'date_maturity': False,         'account_id': receivable_4.id,      'partner_id': cls.partner_b.id}),
                # -200.0 in 31 - 60
                Command.create({'debit': 0.0,       'credit': 800.0,    'date_maturity': '2017-01-01',  'account_id': receivable_5.id,      'partner_id': cls.partner_b.id}),
                # Ignored line.
                Command.create({'debit': 0.0,       'credit': 200.0,    'date_maturity': False,         'account_id': misc_2.id,            'partner_id': cls.partner_b.id}),
            ],
        })

        move_4 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-10-05'),
            'invoice_date': fields.Date.from_string('2016-10-05'),
            'journal_id': cls.company_data_2['default_journal_sale'].id,
            'line_ids': [
                # -200.0 in 61 - 90
                Command.create({'debit': 0.0,       'credit': 200.0,    'date_maturity': '2016-12-02',  'account_id': receivable_4.id,      'partner_id': cls.partner_b.id}),
                # -300.0 in 31 - 60
                Command.create({'debit': 0.0,       'credit': 300.0,    'date_maturity': '2016-12-03',  'account_id': receivable_4.id,      'partner_id': cls.partner_b.id}),
                # 1000.0 in 91 - 120
                Command.create({'debit': 1000.0,    'credit': 0.0,      'date_maturity': False,         'account_id': receivable_5.id,      'partner_id': cls.partner_b.id}),
                # 100.0 in all dates
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2017-02-01',  'account_id': receivable_6.id,      'partner_id': cls.partner_b.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2017-01-02',  'account_id': receivable_6.id,      'partner_id': cls.partner_b.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-12-03',  'account_id': receivable_6.id,      'partner_id': cls.partner_b.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-11-03',  'account_id': receivable_6.id,      'partner_id': cls.partner_b.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-10-04',  'account_id': receivable_6.id,      'partner_id': cls.partner_b.id}),
                Command.create({'debit': 100.0,     'credit': 0.0,      'date_maturity': '2016-01-01',  'account_id': receivable_6.id,      'partner_id': cls.partner_b.id}),
                # Ignored line.
                Command.create({'debit': 0.0,       'credit': 1100.0,   'date_maturity': False,         'account_id': misc_2.id,            'partner_id': cls.partner_b.id}),
            ],
        })
        (move_3 + move_4).action_post()
        (move_3 + move_4).line_ids.filtered(lambda line: line.account_id == receivable_4).reconcile()
        (move_3 + move_4).line_ids.filtered(lambda line: line.account_id == receivable_5).reconcile()
        cls.env['res.currency'].search([('name', '!=', 'USD')]).with_context(force_deactivate=True).active = False
        companies = cls.company_data['company'] + cls.company_data_2['company']
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=companies.ids))
        cls.report = cls.env.ref('account_reports.aged_receivable_report')
        cls.parent_line_id = cls._get_basic_line_dict_id_from_report_line_ref("account_reports.aged_receivable_line")

    def test_aged_receivable_unfold_1_whole_report(self):
        """ Test unfolding a line when rendering the whole report. """
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01')
        partner_a_line_id = self.report._get_generic_line_id('res.partner', self.partner_a.id, parent_line_id=self.parent_line_id, markup={'groupby': 'partner_id'})
        options['unfolded_lines'] = [partner_a_line_id]

        # Sort by Invoice Date
        options['order_column'] = {
            'expression_label': 'invoice_date',
            'direction': 'ASC',
        }

        report_lines = self.report._get_lines(options)

        sorted_report_lines = self.report._sort_lines(report_lines, options)
        self.assertLinesValues(
            # pylint: disable=C0326
            sorted_report_lines,
            #   Name                    Not Due On      1 - 30     31 - 60     61 - 90    91 - 120      Older         Total
            [   0,                               3,          4,          5,          6,          7,         8,            9],
            [
                ('Aged Receivable',          150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
                ('partner_a',                100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',           100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('INV/2016/00002',             0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('Total partner_a',          100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('partner_b',                 50.0,      50.0,        50.0,       300.0,     150.0,       50.0,       650.0),
                ('Total Aged Receivable',    150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options,
        )

        # Sort 61 - 90 decreasing.
        options['order_column'] = {
            'expression_label': 'period3',
            'direction': 'DESC',
        }

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(sorted_report_lines, options),
            #   Name                    Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older       Total
            [   0,                               3,          4,          5,          6,          7,          8,          9],
            [
                ('Aged Receivable',          150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
                ('partner_a',                100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('INV/2016/00002',             0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',           100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('Total partner_a',          100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('partner_b',                 50.0,       50.0,       50.0,      300.0,      150.0,       50.0,       650.0),
                ('Total Aged Receivable',    150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options,
        )

        # Sort 61 - 90 increasing.
        options['order_column'] = {
            'expression_label': 'period3',
            'direction': 'ASC',
        }

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(sorted_report_lines, options),
            #   Name                    Not Due On      1 - 30     31 - 60      61 - 90    91 - 120       Older       Total
            [   0,                               3,          4,          5,           6,          7,          8,          9],
            [
                ('Aged Receivable',          150.0,      150.0,      150.0,       900.0,      450.0,      150.0,      1950.0),
                ('partner_b',                 50.0,       50.0,       50.0,       300.0,      150.0,       50.0,       650.0),
                ('partner_a',                100.0,      100.0,      100.0,       600.0,      300.0,      100.0,      1300.0),
                ('INV/2016/00001',             0.0,        0.0,        0.0,         0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',           100.0,        0.0,        0.0,         0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,      100.0,        0.0,         0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,      100.0,         0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,         0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,         0.0,        0.0,      100.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,       100.0,        0.0,        0.0,          ''),
                ('INV/2016/00002',             0.0,        0.0,        0.0,       500.0,        0.0,        0.0,          ''),
                ('Total partner_a',          100.0,      100.0,      100.0,       600.0,      300.0,      100.0,      1300.0),
                ('Total Aged Receivable',    150.0,      150.0,      150.0,       900.0,      450.0,      150.0,      1950.0),
            ],
            options,
        )

    def test_aged_receivable_unfold_all(self):
        default_options = {
            'unfold_all': True,
            'order_column': {
                'expression_label': 'invoice_date',
                'direction': 'ASC',
            }
        }
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01', default_options=default_options)

        report_lines = self.report._get_lines(options)

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(report_lines, options),
            #   Name                   Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                              3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',         150.0,      150.0,      150.0,       900.0,     450.0,      150.0,      1950.0),
                ('partner_a',               100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('INV/2016/00001',            0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',          100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('INV/2016/00002',            0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('Total partner_a',         100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('partner_b',                50.0,       50.0,       50.0,       300.0,     150.0,       50.0,       650.0),
                ('INV/2016/00001',            0.0,        0.0,        0.0,         0.0,     100.0,        0.0,          ''),
                ('INV/2016/00001',           50.0,        0.0,        0.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,       50.0,        0.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,       50.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,        50.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,         0.0,      50.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,         0.0,       0.0,       50.0,          ''),
                ('INV/2016/00002',            0.0,        0.0,        0.0,       250.0,       0.0,        0.0,          ''),
                ('Total partner_b',          50.0,       50.0,       50.0,       300.0,     150.0,       50.0,       650.0),
                ('Total Aged Receivable',   150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options
        )

    def test_aged_receivable_unfold_all_with_integer_rounding(self):
        """ Test unfolding a line when rendering the whole report with integer rounding. """
        self.report.integer_rounding = 'HALF-UP'
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01')
        partner_a_line_id = self.report._get_generic_line_id('res.partner', self.partner_a.id, parent_line_id=self.parent_line_id, markup={'groupby': 'partner_id'})
        options['unfolded_lines'] = [partner_a_line_id]
        report_lines = self.report._get_lines(options)
        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(report_lines, options),
            #   Name                   Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                              3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',         150.0,      150.0,      150.0,       900.0,     450.0,      150.0,      1950.0),
                ('partner_a',               100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('INV/2016/00001',            0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',          100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',            0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('INV/2016/00002',            0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('Total partner_a',         100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('partner_b',                50.0,       50.0,       50.0,       300.0,     150.0,       50.0,       650.0),
                ('Total Aged Receivable',   150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options
        )

    def test_aged_receivable_unknown_partner(self):
        """ Test that journal items without a partner in the receivable account appear as unknown partner. """

        misc_move = self.env['account.move'].create({
            'date': '2017-03-31',
            'line_ids': [
                Command.create({'debit': 1000.0, 'credit': 0.0, 'account_id': self.company_data['default_account_revenue'].id}),
                Command.create({'debit': 0.0, 'credit': 1000.0, 'account_id': self.company_data['default_account_receivable'].id}),
            ],
        })
        misc_move.action_post()

        options = self._generate_options(self.report, '2017-03-01', '2017-04-01')
        self.env.company.totals_below_sections = False

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name              Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                         3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',      0.0,    -1000.0,      150.0,      150.0,      150.0,     1500.0,       950.0),
                ('partner_a',            0.0,        0.0,      100.0,      100.0,      100.0,     1000.0,      1300.0),
                ('partner_b',            0.0,        0.0,       50.0,       50.0,       50.0,      500.0,       650.0),
                ('Unknown',              0.0,    -1000.0,        0.0,        0.0,        0.0,        0.0,     -1000.0),
            ],
            options,
        )

    def test_aged_receivable_filter_partners(self):
        """ Test the filter on top allowing to filter on res.partner. """
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01')
        options['partner_ids'] = self.partner_a.ids
        self.env.company.totals_below_sections = False

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name             Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                        3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',   100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('partner_a',         100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
            ],
            options,
        )

    def test_aged_receivable_filter_partner_categories(self):
        """ Test the filter on top allowing to filter on res.partner.category. """
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01')
        options['partner_categories'] = self.partner_category_a.ids
        self.env.company.totals_below_sections = False

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name              Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                         3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',    150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
                ('partner_a',          100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('partner_b',           50.0,       50.0,       50.0,      300.0,      150.0,       50.0,       650.0),
            ],
            options,
        )

    def test_aged_receivable_reconciliation_date(self):
        """ Check the values at a date before some reconciliations are done. """
        options = self._generate_options(self.report, '2016-10-31', '2016-10-31')
        options['recon_date'] = {'date_to': '2016-10-31'}
        self.env.company.totals_below_sections = False

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name             Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                        3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable', -133.33,    1466.67,        0.0,        0.0,        0.0,     133.33,     1466.67),
                ('partner_a',       -100.00,    1100.00,        0.0,        0.0,        0.0,     100.00,     1100.00),
                ('partner_b',        -33.33,     366.67,        0.0,        0.0,        0.0,      33.33,      366.67),
            ],
            options,
        )

    # TODO: move these tests into a generic report test class
    def test_aged_receivable_sort_lines_by_date(self):
        """ Test the _sort_lines function using date as sort key. """
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01')
        partner_a_line_id = self.report._get_generic_line_id('res.partner', self.partner_a.id, parent_line_id=self.parent_line_id, markup={'groupby': 'partner_id'})
        partner_b_line_id = self.report._get_generic_line_id('res.partner', self.partner_b.id, parent_line_id=self.parent_line_id, markup={'groupby': 'partner_id'})
        options['unfolded_lines'] = [partner_a_line_id, partner_b_line_id]

        # Sort by Invoice Date increasing
        options['order_column'] = {
            'expression_label': 'invoice_date',
            'direction': 'ASC',
        }

        report_lines = self.report._get_lines(options)

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(report_lines, options),
            #   Name                    Invoice Date  Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                                 1,          3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',              '',       150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
                ('partner_a',                    '',       100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',      100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('INV/2016/00002',      '11/03/2016',        0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('Total partner_a',               '',      100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('partner_b',                     '',       50.0,       50.0,       50.0,       300.0,     150.0,       50.0,       650.0),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,         0.0,     100.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',       50.0,        0.0,        0.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,       50.0,        0.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,       50.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,        50.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,         0.0,      50.0,        0.0,          ''),
                ('INV/2016/00001',      '10/05/2016',        0.0,        0.0,        0.0,         0.0,       0.0,       50.0,          ''),
                ('INV/2016/00002',      '11/03/2016',        0.0,        0.0,        0.0,       250.0,       0.0,        0.0,          ''),
                ('Total partner_b',               '',       50.0,       50.0,       50.0,       300.0,     150.0,       50.0,       650.0),
                ('Total Aged Receivable',         '',      150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options,
        )

        # Sort by Invoice Date decreasing
        options['order_column'] = {
            'expression_label': 'invoice_date',
            'direction': 'DESC',
        }

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(report_lines, options),
            #   Name                     Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                                3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',           150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
                ('partner_a',                 100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('INV/2016/00002',              0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',            100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('Total partner_a',           100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('partner_b',                  50.0,       50.0,       50.0,       300.0,     150.0,       50.0,       650.0),
                ('INV/2016/00002',              0.0,        0.0,        0.0,       250.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,         0.0,     100.0,        0.0,          ''),
                ('INV/2016/00001',             50.0,        0.0,        0.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,       50.0,        0.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,       50.0,         0.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,        50.0,       0.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,         0.0,      50.0,        0.0,          ''),
                ('INV/2016/00001',              0.0,        0.0,        0.0,         0.0,       0.0,       50.0,          ''),
                ('Total partner_b',            50.0,       50.0,       50.0,       300.0,     150.0,       50.0,       650.0),
                ('Total Aged Receivable',     150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options,
        )

    def test_aged_receivable_sort_lines_by_numeric_value(self):
        """ Test the _sort_lines function using float as sort key. """
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01')
        partner_a_line_id = self.report._get_generic_line_id('res.partner', self.partner_a.id, parent_line_id=self.parent_line_id, markup={'groupby': 'partner_id'})
        partner_b_line_id = self.report._get_generic_line_id('res.partner', self.partner_b.id, parent_line_id=self.parent_line_id, markup={'groupby': 'partner_id'})
        options['unfolded_lines'] = [partner_a_line_id, partner_b_line_id]

        # Sort by Not Due On increasing
        options['order_column'] = {
            'expression_label': 'period0',
            'direction': 'ASC',
        }

        report_lines = self.report._get_lines(options)

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(report_lines, options),
            #   Name                    Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                               3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',          150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
                ('partner_b',                 50.0,       50.0,       50.0,      300.0,      150.0,       50.0,       650.0),
                ('INV/2016/00002',             0.0,        0.0,        0.0,      250.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,       50.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,       50.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,       50.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,       50.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,        0.0,       50.0,          ''),
                ('INV/2016/00001',            50.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('Total partner_b',           50.0,       50.0,       50.0,      300.0,      150.0,       50.0,       650.0),
                ('partner_a',                100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('INV/2016/00002',             0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',             0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('INV/2016/00001',           100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('Total partner_a',          100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('Total Aged Receivable',    150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options,
        )

        # Sort by Not Due On decreasing
        options['order_column'] = {
            'expression_label': 'period0',
            'direction': 'DESC',
        }

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._sort_lines(report_lines, options),
            #   Name                 Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older       Total
            [   0,                            3,          4,          5,          6,          7,          8,          9],
            [
                ('Aged Receivable',       150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
                ('partner_a',             100.0,      100.0,      100.0,      600.0,      300.0,      100.0,      1300.0),
                ('INV/2016/00001',        100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00002',          0.0,        0.0,        0.0,      500.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,        0.0,      200.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,      100.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,      100.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,      100.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,        0.0,        0.0,      100.0,          ''),
                ('Total partner_a',       100.0,      100.0,      100.0,       600.0,     300.0,      100.0,      1300.0),
                ('partner_b',              50.0,       50.0,       50.0,      300.0,      150.0,       50.0,       650.0),
                ('INV/2016/00001',         50.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00002',          0.0,        0.0,        0.0,      250.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,        0.0,      100.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,       50.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,       50.0,        0.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,       50.0,        0.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,        0.0,       50.0,        0.0,          ''),
                ('INV/2016/00001',          0.0,        0.0,        0.0,        0.0,        0.0,       50.0,          ''),
                ('Total partner_b',        50.0,       50.0,       50.0,      300.0,      150.0,       50.0,       650.0),
                ('Total Aged Receivable', 150.0,      150.0,      150.0,      900.0,      450.0,      150.0,      1950.0),
            ],
            options,
        )

    def test_aged_receivable_zero_balanced_without_reconciliation(self):
        options = self._generate_options(self.report, '2010-01-01', '2010-01-01', default_options={'unfold_all': True})
        options['recon_date'] = {'date_to': '2010-01-01'}
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2010-01-01',
            'invoice_date_due': '2010-01-01',
            'payment_reference': 'I',
            'invoice_line_ids': [Command.create({
                'name': 'test invoice',
                'price_unit': 100,
                'tax_ids': [],
            })]
        })
        invoice.action_post()

        refund = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.partner_a.id,
            'invoice_date': '2010-01-01',
            'invoice_date_due': '2010-01-01',
            'payment_reference': 'R',
            'invoice_line_ids': [Command.create({
                'name': 'test refund',
                'price_unit': 100,
                'tax_ids': [],
            })]
        })
        refund.action_post()

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name                  Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                             3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',          0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                ('partner_a',                0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                (f"{refund.name} R",      -100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                (f"{invoice.name} I",      100.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('Total partner_a',          0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                ('Total Aged Receivable',    0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
            ],
            options,
        )

        # It should still work if both  invoice and refund are partially reconciled with the same amount
        self.env['account.payment.register'].with_context(active_ids=invoice.ids, active_model='account.move').create({
            'amount': 42,
            'payment_date': '2010-01-01',
            'payment_method_line_id': self.outbound_payment_method_line.id,
        })._create_payments()

        self.env['account.payment.register'].with_context(active_ids=refund.ids, active_model='account.move').create({
            'amount': 42,
            'payment_date': '2010-01-01',
            'payment_method_line_id': self.outbound_payment_method_line.id,
        })._create_payments()

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name                  Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                             3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',          0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                ('partner_a',                0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                (f"{refund.name} R",       -58.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                (f"{invoice.name} I",       58.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('Total partner_a',          0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                ('Total Aged Receivable',    0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
            ],
            options,
        )

        # It should still work if both  invoice and refund are fully reconciled in the future
        self.env['account.payment.register'].with_context(active_ids=invoice.ids, active_model='account.move').create({
            'amount': 58,
            'payment_date': '2020-01-01',
            'payment_method_line_id': self.outbound_payment_method_line.id,
        })._create_payments()

        self.env['account.payment.register'].with_context(active_ids=refund.ids, active_model='account.move').create({
            'amount': 58,
            'payment_date': '2020-01-01',
            'payment_method_line_id': self.outbound_payment_method_line.id,
        })._create_payments()

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name                  Not Due On      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                             3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',          0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                ('partner_a',                0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                (f"{refund.name} R",       -58.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                (f"{invoice.name} I",       58.0,        0.0,        0.0,        0.0,        0.0,        0.0,          ''),
                ('Total partner_a',          0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                ('Total Aged Receivable',    0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
            ],
            options,
        )

    def test_aged_receivable_partial_reconcile_currency(self):
        """ Check that 'Amount Currency' column values are displayed and computed correctly. """
        foreign_partner = self.env['res.partner'].create({'name': 'foreign_partner'})
        currency = self.other_currency
        currency.active = True
        self.env.company.totals_below_sections = False

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': '2023-05-01',
            'invoice_date_due': '2023-05-01',
            'partner_id': foreign_partner.id,
            'currency_id': currency.id,
            'invoice_line_ids': [Command.create({
                'name': 'test',
                'quantity': 1,
                'price_unit': 100.0,
                'tax_ids': [],
            })],
        })
        invoice.action_post()

        self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'amount': 10.0,
            'currency_id': currency.id,
            'payment_date': '2023-05-05',
            'partner_id': foreign_partner.id,
        })._create_payments()

        line_id = self.report._get_generic_line_id('res.partner', foreign_partner.id, markup={'groupby': 'partner_id'}, parent_line_id=self.parent_line_id)
        options = self._generate_options(self.report, '2023-01-01', '2023-05-01')
        options['unfolded_lines'] = [line_id]
        options['recon_date'] = {'date_to': '2023-05-01'}

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_unfolded_lines(self.report._get_lines(options), line_id),
            #   Name                                      Due Date     Amount Currency     Currency     As Of     Total
            [   0,                                               1,                  2,           3,        5,       11],
            [
                ('foreign_partner',                             '',                 '',          '',     50.0,     50.0),
                ('INV/2023/00001',                    '05/01/2023',              100.0,       'CAD',     50.0,       ''),
            ],
			options,
            currency_map={
                2: {'currency': currency},
            },
        )

        new_options = self._generate_options(self.report, '2023-01-01', '2023-05-05')
        new_options['unfolded_lines'] = [line_id]

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_unfolded_lines(self.report._get_lines(new_options), line_id),
            #   Name                                      Due Date     Amount Currency     Currency     As Of     1-30     Total
            [   0,                                               1,                  2,           3,        5,       6,       11],
            [
                ('foreign_partner',                             '',                 '',          '',      0.0,    45.0,     45.0),
                ('INV/2023/00001',                    '05/01/2023',               90.0,       'CAD',      0.0,    45.0,       ''),
            ],
			options,
            currency_map={
                2: {'currency': currency},
            },
        )

    def test_aged_receivable_aging_interval(self):
        options = self._generate_options(self.report, '2017-02-01', '2017-02-01')
        initial_report_lines = self.report._get_lines(options)

        # With the default interval of 30
        self.assertLinesValues(
            self.report._sort_lines(initial_report_lines, options),
            #   Name                  Not Due On      1 - 30      31 - 60      62 - 90    91 - 120       Older      Total
            [   0,                             3,          4,           5,           6,          7,          8,         9],
            [
                ('Aged Receivable',        150.0,      150.0,       150.0,       900.0,      450.0,      150.0,    1950.0),
                ('partner_a',              100.0,      100.0,       100.0,       600.0,      300.0,      100.0,    1300.0),
                ('partner_b',               50.0,       50.0,        50.0,       300.0,      150.0,       50.0,     650.0),
                ('Total Aged Receivable',  150.0,      150.0,       150.0,       900.0,      450.0,      150.0,    1950.0),
            ],
            options
        )

        options['aging_interval'] = 60
        report_lines = self.report._get_lines(options)

        # With the interval of 60
        self.assertLinesValues(
            self.report._sort_lines(report_lines, options),
            #   Name                  Not Due On      1 - 60    61 - 120   121 - 180   181 - 240       Older        Total
            [   0,                             3,          4,          5,          6,          7,          8,           9],
            [
                ('Aged Receivable',        150.0,      300.0,     1350.0,         0.0,       0.0,      150.0,      1950.0),
                ('partner_a',              100.0,      200.0,      900.0,         0.0,       0.0,      100.0,      1300.0),
                ('partner_b',               50.0,      100.0,      450.0,         0.0,       0.0,       50.0,       650.0),
                ('Total Aged Receivable',  150.0,      300.0,     1350.0,         0.0,       0.0,      150.0,      1950.0),
            ],
            options
        )

    def test_aged_receivable_horizontal_groups(self):
        horizontal_group = self.env['account.report.horizontal.group'].create({
            'name': 'Horizontal Group total',
            'rule_ids': [
                Command.create({
                    'field_name': 'company_id',
                    'domain': f"[('id', 'in', {(self.company_data['company'] + self.company_data_2['company']).ids})]",
                }),
            ],
            'report_ids': self.report
        })
        options = self._generate_options(self.report, '2017-03-01', '2017-04-01', default_options={'selected_horizontal_group_id': horizontal_group.id})
        self.env.company.totals_below_sections = False

        self.assertLinesValues(
            # pylint: disable=C0326
            self.report._get_lines(options),
            #   Name                 At Date      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total      At Date      1 - 30     31 - 60     61 - 90    91 - 120       Older        Total
            [   0,                         3,          4,          5,          6,          7,          8,           9,          12,         13,         14,         15,         16,         17,          18],
            [
            ('Aged Receivable',          0.0,        0.0,      100.0,      100.0,      100.0,     1000.0,      1300.0,         0.0,        0.0,       50.0,       50.0,       50.0,      500.0,       650.0),
                ('partner_a',            0.0,        0.0,      100.0,      100.0,      100.0,     1000.0,      1300.0,         0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0),
                ('partner_b',            0.0,        0.0,        0.0,        0.0,        0.0,        0.0,         0.0,         0.0,        0.0,       50.0,       50.0,       50.0,      500.0,       650.0),
            ],
            options,
        )
