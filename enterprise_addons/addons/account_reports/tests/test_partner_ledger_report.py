# pylint: disable=C0326
from .common import TestAccountReportsCommon

from odoo import Command, fields
from odoo.fields import Domain
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPartnerLedgerReport(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_category_a = cls.env['res.partner.category'].create({'name': 'partner_categ_a'})
        cls.partner_category_b = cls.env['res.partner.category'].create({'name': 'partner_categ_b'})

        cls.partner_a.write({'category_id': [Command.set([cls.partner_category_a.id, cls.partner_category_b.id])]})
        cls.partner_b.write({'category_id': [Command.set([cls.partner_category_a.id])]})
        cls.partner_c = cls._create_partner(name='partner_c', category_id=[Command.set([cls.partner_category_b.id])])

        # Entries in 2016 for company_1 to test the initial balance.
        cls.move_2016_1 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-01-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 100.0,     'credit': 0.0,      'name': '2016_1_1',     'account_id': cls.company_data['default_account_payable'].id,       'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 200.0,     'credit': 0.0,      'name': '2016_1_1',     'account_id': cls.company_data['default_account_payable'].id,       'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 0.0,       'credit': 300.0,    'name': '2016_1_2',     'account_id': cls.company_data['default_account_receivable'].id,    'partner_id': cls.partner_c.id}),
            ],
        })
        cls.move_2016_1.action_post()

        # Entries in 2016 for company_2 to test the initial balance in multi-companies/multi-currencies.
        cls.move_2016_2 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2016-06-01'),
            'journal_id': cls.company_data_2['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 100.0,     'credit': 0.0,      'name': '2016_2_1',     'account_id': cls.company_data_2['default_account_payable'].id,     'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,       'credit': 100.0,    'name': '2016_2_2',     'account_id': cls.company_data_2['default_account_receivable'].id,  'partner_id': cls.partner_c.id}),
            ],
        })
        cls.move_2016_2.action_post()

        # Entry in 2017 for company_1 to test the report at current date.
        cls.move_2017_1 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2017-01-01'),
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 1000.0,    'credit': 0.0,      'name': '2017_1_1',     'account_id': cls.company_data['default_account_payable'].id,       'partner_id': cls.partner_b.id}),
                (0, 0, {'debit': 2000.0,    'credit': 0.0,      'name': '2017_1_2',     'account_id': cls.company_data['default_account_payable'].id,       'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 3000.0,    'credit': 0.0,      'name': '2017_1_3',     'account_id': cls.company_data['default_account_payable'].id,       'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 4000.0,    'credit': 0.0,      'name': '2017_1_4',     'account_id': cls.company_data['default_account_receivable'].id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 5000.0,    'credit': 0.0,      'name': '2017_1_5',     'account_id': cls.company_data['default_account_receivable'].id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 6000.0,    'credit': 0.0,      'name': '2017_1_6',     'account_id': cls.company_data['default_account_receivable'].id,    'partner_id': cls.partner_a.id}),
                (0, 0, {'debit': 0.0,       'credit': 6000.0,   'name': '2017_1_7',     'account_id': cls.company_data['default_account_receivable'].id,    'partner_id': cls.partner_c.id}),
                (0, 0, {'debit': 0.0,       'credit': 7000.0,   'name': '2017_1_8',     'account_id': cls.company_data['default_account_receivable'].id,    'partner_id': cls.partner_c.id}),
                (0, 0, {'debit': 0.0,       'credit': 8000.0,   'name': '2017_1_9',     'account_id': cls.company_data['default_account_receivable'].id,    'partner_id': cls.partner_c.id}),
            ],
        })
        cls.move_2017_1.action_post()

        # Entry in 2017 for company_2 to test the current period in multi-companies/multi-currencies.
        cls.move_2017_2 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2017-06-01'),
            'journal_id': cls.company_data_2['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 400.0,     'credit': 0.0,      'name': '2017_2_1',     'account_id': cls.company_data_2['default_account_receivable'].id}),
                (0, 0, {'debit': 0.0,       'credit': 400.0,    'name': '2017_2_2',     'account_id': cls.company_data_2['default_account_receivable'].id}),
            ],
        })
        cls.move_2017_2.action_post()

        cls.report = cls.env.ref('account_reports.partner_ledger_report')

    def test_partner_ledger_unfold(self):
        ''' Test unfolding a line when rendering the whole report. '''
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,        21200.0,         0.0),
                ('partner_a',                           20000.0,        '',              20150.0),
                ('partner_b',                           1000.0,         '',              1200.0),
                ('partner_c',                           '',             21000.0,         -21350.0),
                ('Unknown Partner',                     200.0,          200.0,           0.0),
                ('Total Partner Ledger',                21200.0,        21200.0,         0.0),
            ],
            options,
        )

        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,        21200.0,        0.0),
                ('partner_a',                           20000.0,        '',             20150.0),
                ('Initial Balance',                     '',             '',             150.0),
                ('MISC/2017/01/0001 2017_1_2',          2000.0,         '',             2150.0),
                ('MISC/2017/01/0001 2017_1_3',          3000.0,         '',             5150.0),
                ('MISC/2017/01/0001 2017_1_4',          4000.0,         '',             9150.0),
                ('MISC/2017/01/0001 2017_1_5',          5000.0,         '',             14150.0),
                ('MISC/2017/01/0001 2017_1_6',          6000.0,         '',             20150.0),
                ('Total partner_a',                     20000.0,        '',             20150.0),
                ('partner_b',                           1000.0,         '',             1200.0),
                ('partner_c',                           '',             21000.0,        -21350.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('Total Partner Ledger',                21200.0,        21200.0,        0.0),
            ],
            options,
        )

    def test_partner_ledger_all_columns(self):
        foreign_currency = self.env.ref('base.EUR')
        foreign_currency.active = True
        self.env['res.currency.rate'].create({
            'name': '2017-01-01',
            'rate': 0.5,
            'currency_id': foreign_currency.id,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'currency_id': foreign_currency.id,
            'invoice_date': '2017-06-06',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'price_unit': 500,
            })],
        })
        invoice.action_post()
        line1_to_reconcile = invoice.line_ids.filtered_domain(Domain('credit', '=', 1000))
        line2_to_reconcile = self.move_2017_1.line_ids.filtered_domain(Domain('debit', '=', 2000))
        (line1_to_reconcile + line2_to_reconcile).reconcile()
        matching_number = line1_to_reconcile.matching_number

        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Journal  Account  Invoice Date  Due Date  Matching  Debit     Credit    Amount CurrencyBalance
            [   0,                                      1,       2,       3,            4,        5,        6,        7,        8,               9],
            [
                ('Partner Ledger',                      '',      '',      '',           '',       '',       21200.0,  22200.0,  '',              -1000.0),
                ('partner_a',                           '',      '',      '',           '',       '',       20000.0,  1000.0,   '',              19150.0),
                ('partner_b',                           '',      '',      '',           '',       '',       1000.0,   '',       '',              1200.0),
                ('partner_c',                           '',      '',      '',           '',       '',       '',       21000.0,  '',              -21350.0),
                ('Unknown Partner',                     '',      '',      '',           '',       '',       200.0,    200.0,    '',              0.0),
                ('Total Partner Ledger',                '',      '',      '',           '',       '',       21200.0,  22200.0,  '',              -1000.0),
            ],
            options,
        )

        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Journal  Account    Invoice Date   Due Date       Matching          Debit     Credit    Amount Currency  Balance
            [   0,                                      1,       2,         3,             4,             5,                6,        7,        8,               9],
            [
                ('Partner Ledger',                      '',      '',        '',            '',            '',               21200.0,  22200.0,  '',              -1000.0),
                ('partner_a',                           '',      '',        '',            '',            '',               20000.0,  1000.0,   '',              19150.0),
                ('Initial Balance',                     '',      '',        '',            '',            '',               '',       '',       '',              150.0),
                ('MISC/2017/01/0001 2017_1_2',          'MISC',  '211000',  '01/01/2017',  '',            matching_number,  2000.0,   '',       '',              2150.0),
                ('MISC/2017/01/0001 2017_1_3',          'MISC',  '211000',  '01/01/2017',  '',            '',               3000.0,   '',       '',              5150.0),
                ('MISC/2017/01/0001 2017_1_4',          'MISC',  '121000',  '01/01/2017',  '',            '',               4000.0,   '',       '',              9150.0),
                ('MISC/2017/01/0001 2017_1_5',          'MISC',  '121000',  '01/01/2017',  '',            '',               5000.0,   '',       '',              14150.0),
                ('MISC/2017/01/0001 2017_1_6',          'MISC',  '121000',  '01/01/2017',  '',            '',               6000.0,   '',       '',              20150.0),
                ('BILL/2017/06/0001',                   'BILL',  '211000',  '06/06/2017',  '06/06/2017',  matching_number,  '',       1000.0,   -500.0,          19150.0),
                ('Total partner_a',                     '',      '',        '',            '',            '',               20000.0,  1000.0,   '',              19150.0),
                ('partner_b',                           '',      '',        '',            '',            '',               1000.0,   '',       '',              1200.0),
                ('partner_c',                           '',      '',        '',            '',            '',               '',       21000.0,  '',              -21350.0),
                ('Unknown Partner',                     '',      '',        '',            '',            '',               200.0,    200.0,    '',              0.0),
                ('Total Partner Ledger',                '',      '',        '',            '',            '',               21200.0,  22200.0,  '',              -1000.0),
            ],
            options,
            currency_map={
                8: {'currency': foreign_currency},
            },
        )

    def test_partner_ledger_batch_data_generator(self):
        """ Test the custom_unfold_all_batch_data_generator """
        options = self._generate_options(
            self.report,
            fields.Date.from_string('2017-01-01'),
            fields.Date.from_string('2017-12-31'),
            default_options={'unfold_all': True, 'test_unfold_all': True}
        )

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                      Debit           Credit          Balance
            [   0,                                          6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,       21200.0,             0.0),
                ('partner_a',                           20000.0,            '',          20150.0),
                ('Initial Balance',                          '',            '',           150.0),
                ('MISC/2017/01/0001 2017_1_2',           2000.0,            '',          2150.0),
                ('MISC/2017/01/0001 2017_1_3',           3000.0,            '',          5150.0),
                ('MISC/2017/01/0001 2017_1_4',           4000.0,            '',          9150.0),
                ('MISC/2017/01/0001 2017_1_5',           5000.0,            '',         14150.0),
                ('MISC/2017/01/0001 2017_1_6',           6000.0,            '',         20150.0),
                ('Total partner_a',                     20000.0,            '',         20150.0),
                ('partner_b',                            1000.0,            '',          1200.0),
                ('Initial Balance',                          '',            '',           200.0),
                ('MISC/2017/01/0001 2017_1_1',           1000.0,            '',          1200.0),
                ('Total partner_b',                      1000.0,            '',          1200.0),
                ('partner_c',                                '',       21000.0,        -21350.0),
                ('Initial Balance',                          '',            '',          -350.0),
                ('MISC/2017/01/0001 2017_1_7',               '',        6000.0,         -6350.0),
                ('MISC/2017/01/0001 2017_1_8',               '',        7000.0,        -13350.0),
                ('MISC/2017/01/0001 2017_1_9',               '',        8000.0,        -21350.0),
                ('Total partner_c',                          '',       21000.0,        -21350.0),
                ('Unknown Partner',                       200.0,         200.0,             0.0),
                ('MISC/2017/06/0001 2017_2_1',            200.0,            '',           200.0),
                ('MISC/2017/06/0001 2017_2_2',               '',         200.0,             0.0),
                ('Total Unknown Partner',                 200.0,         200.0,             0.0),
                ('Total Partner Ledger',                21200.0,       21200.0,             0.0),
            ],
            options,
        )

    def test_partner_ledger_load_more(self):
        ''' Test unfolding a line to use the load more. '''
        self.report.load_more_limit = 2

        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')
        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        report_lines = self.report._get_lines(options)

        self.assertLinesValues(
            report_lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,        21200.0,        0.0),
                ('partner_a',                           20000.0,        '',             20150.0),
                ('Initial Balance',                     '',             '',             150.0),
                ('MISC/2017/01/0001 2017_1_2',          2000.0,         '',             2150.0),
                ('4 more',                              18000.0,        0.00,           20150.0),
                ('Total partner_a',                     20000.0,        '',             20150.0),
                ('partner_b',                           1000.0,         '',             1200.0),
                ('2 more',                              200.0,          21200.0,        -21350),
                ('Total Partner Ledger',                21200.0,        21200.0,        0.0),
            ],
            options,
        )

        load_more_partner_a = self.report.get_expanded_lines(
            options,
            report_lines[1].id,
            report_lines[4].groupby,
            '_report_expand_unfoldable_line_with_groupby',
            None,
            None,
            ignore_load_more=True
        )

        self.assertLinesValues(
            load_more_partner_a,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Initial Balance',                     '',             '',             150.0),
                ('MISC/2017/01/0001 2017_1_2',          2000.0,         '',             2150.0),
                ('MISC/2017/01/0001 2017_1_3',          3000.0,         '',             5150.0),
                ('MISC/2017/01/0001 2017_1_4',          4000.0,         '',             9150.0),
                ('MISC/2017/01/0001 2017_1_5',          5000.0,         '',             14150.0),
                ('MISC/2017/01/0001 2017_1_6',          6000.0,         '',             20150.0),
            ],
            options,
        )

        load_more_all_partners = self.report.get_expanded_lines(
            options,
            report_lines[0].id,
            report_lines[8].groupby,  # Index 7 is the total of partner_b
            '_report_expand_unfoldable_line_with_groupby',
            None,
            None,
            ignore_load_more=True
        )

        self.assertLinesValues(
            load_more_all_partners,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('partner_a',                           20000.0,        '',             20150.0),
                ('Initial Balance',                     '',             '',             150.0),
                ('MISC/2017/01/0001 2017_1_2',          2000.0,         '',             2150.0),
                ('4 more',                              18000.0,        0.00,           20150.0),
                ('Total partner_a',                     20000.0,        '',             20150.0),
                ('partner_b',                           1000.0,         '',             1200.0),
                ('partner_c',                           '',             21000.0,        -21350.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
            ],
            options,
        )

    def test_partner_ledger_filter_account_types(self):
        ''' Test building the report with a filter on account types.
        When filtering on receivable accounts (i.e. trade_receivable and/or non_trade_receivable), partner_b should disappear from the report.
        '''
        options = self._generate_options(self.report, fields.Date.from_string('2017-01-01'), fields.Date.from_string('2017-12-31'))
        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]
        options = self._update_multi_selector_filter(options, 'account_type', ['non_trade_receivable', 'trade_receivable'])

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      15200.0,        21200.0,        -6350.0),
                ('partner_a',                           15000.0,        '',             15000.0),
                ('MISC/2017/01/0001 2017_1_4',          4000.0,         '',             4000.0),
                ('MISC/2017/01/0001 2017_1_5',          5000.0,         '',             9000.0),
                ('MISC/2017/01/0001 2017_1_6',          6000.0,         '',             15000.0),
                ('Total partner_a',                     15000.0,        '',             15000.0),
                ('partner_c',                           '',             21000.0,        -21350.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('Total Partner Ledger',                15200.0,        21200.0,        -6350.0),
            ],
            options,
        )

    def test_partner_ledger_filter_partners(self):
        ''' Test the filter on top allowing to filter on res.partner.'''
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')
        options['partner_ids'] = (self.partner_a + self.partner_c).ids

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                       20000.0,        21000.0,        -1200.00),
                ('partner_a',                            20000.0,             '',        20150.0),
                ('partner_c',                                 '',        21000.0,       -21350.0),
                ('Total Partner Ledger',                 20000.0,        21000.0,        -1200.00),
            ],
            options,
        )

    def test_partner_ledger_filter_partner_categories(self):
        ''' Test the filter on top allowing to filter on res.partner.category.'''
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')
        options['partner_categories'] = self.partner_category_a.ids

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21000.0,        '',             21350.0),
                ('partner_a',                           20000.0,        '',             20150.0),
                ('partner_b',                           1000.0,         '',             1200.0),
                ('Total Partner Ledger',                21000.0,        '',             21350.0),
            ],
            options,
        )

    def test_partner_ledger_unknown_partner(self):
        ''' Test the partner ledger for whenever a line appearing in it has no partner assigned.
        Check that reconciling this line with an invoice/bill of a partner does affect his balance.
        '''
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')

        misc_move = self.env['account.move'].create({
            'date': '2017-03-31',
            'line_ids': [
                (0, 0, {'debit': 1000.0, 'credit': 0.0,    'account_id': self.company_data['default_account_revenue'].id}),
                (0, 0, {'debit': 0.0,    'credit': 1000.0, 'account_id': self.company_data['default_account_receivable'].id}),
            ],
        })
        misc_move.action_post()

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                       21200.0,        22200.0,        -1000.00),
                ('partner_a',                            20000.0,             '',       20150.0),
                ('partner_b',                            1000.00,             '',        1200.00),
                ('partner_c',                                 '',        21000.0,      -21350.0),
                ('Unknown Partner',                       200.00,        1200.00,       -1000.00),
                ('Total Partner Ledger',                 21200.0,        22200.0,       -1000.00),
            ],
            options,
        )

        debit_line = self.move_2017_1.line_ids.filtered(lambda line: line.debit == 4000.0)
        credit_line = misc_move.line_ids.filtered(lambda line: line.credit == 1000.0)
        (debit_line + credit_line).reconcile()

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                       22200.0,        23200.0,       -1000.00),
                ('partner_a',                           20000.0,         1000.00,       19150.0),
                ('partner_b',                            1000.00,             '',        1200.00),
                ('partner_c',                                 '',       21000.0,       -21350.0),
                ('Unknown Partner',                      1200.00,        1200.00,           0.00),
                ('Total Partner Ledger',                22200.0,        23200.0,        -1000.00),
            ],
            options,
        )

        # Unfold 'partner_a'
        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                       22200.0,        23200.0,       -1000.0),
                ('partner_a',                            20000.0,        1000.00,       19150.0),
                ('Initial Balance',                           '',             '',         150.0),
                ('MISC/2017/01/0001 2017_1_2',           2000.00,             '',        2150.0),
                ('MISC/2017/01/0001 2017_1_3',           3000.00,             '',        5150.0),
                ('MISC/2017/01/0001 2017_1_4',           4000.00,             '',        9150.0),
                ('MISC/2017/01/0001 2017_1_5',           5000.00,             '',       14150.0),
                ('MISC/2017/01/0001 2017_1_6',           6000.00,             '',       20150.0),
                ('MISC/2017/03/0001',                         '',        1000.00,       19150.0),
                ('Total partner_a',                      20000.0,        1000.00,       19150.0),
                ('partner_b',                            1000.00,             '',        1200.00),
                ('partner_c',                                 '',        21000.0,      -21350.0),
                ('Unknown Partner',                      1200.00,        1200.00,           0.00),
                ('Total Partner Ledger',                 22200.0,        23200.0,       -1000.00),
            ],
            options,
        )

        # Unfold 'Unknown'
        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        unknown_line_id = self.report._get_generic_line_id(model_name='res.partner', value=None, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [unknown_line_id]

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                       22200.0,        23200.0,       -1000.00),
                ('partner_a',                            20000.0,        1000.00,       19150.0),
                ('partner_b',                            1000.00,             '',        1200.00),
                ('partner_c',                                 '',        21000.0,      -21350.0),
                ('Unknown Partner',                      1200.00,        1200.00,           0.00),
                ('MISC/2017/03/0001',                    1000.00,             '',        1000.00),
                ('MISC/2017/03/0001',                         '',        1000.00,           0.00),
                ('MISC/2017/06/0001 2017_2_1',            200.00,             '',         200.00),
                ('MISC/2017/06/0001 2017_2_2',                '',         200.00,           0.00),
                ('Total Unknown Partner',                1200.00,        1200.00,           0.00),
                ('Total Partner Ledger',                 22200.0,        23200.0,       -1000.00),
            ],
            options,
        )

        # Change the dates to exclude the reconciliation max date: situation is back to the beginning
        options = self._generate_options(self.report, '2017-01-01', '2017-03-30')

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                       21000.0,        21000.0,           0.00),
                ('partner_a',                            20000.0,             '',       20150.0),
                ('partner_b',                            1000.00,             '',        1200.00),
                ('partner_c',                                 '',        21000.0,      -21350.0),
                ('Total Partner Ledger',                 21000.0,        21000.0,           0.00)
            ],
            options,
        )

        # Change the dates to have a date_from > to the reconciliation max date and check the initial balances are correct
        options = self._generate_options(self.report, '2017-04-01', '2017-04-01')
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      '',              '',            -1000.0),
                ('partner_a',                           '',              '',            19150.0),
                ('partner_b',                           '',              '',            1200.00),
                ('partner_c',                           '',              '',            -21350.0),
                ('Total Partner Ledger',                '',              '',            -1000.0),
            ],
            options,
        )

        # Unfold 'partner_a' to check the initial balance line is correct
        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      '',             '',           -1000.0),
                ('partner_a',                           '',             '',            19150.0),
                ('Initial Balance',                     '',             '',             19150.0),
                ('Total partner_a',                     '',             '',            19150.0),
                ('partner_b',                           '',             '',            1200.0),
                ('partner_c',                           '',             '',           -21350.0),
                ('Total Partner Ledger',                '',             '',           -1000.0),
            ],
            options,
        )

    def test_partner_ledger_user_groupby(self):
        self.report.line_ids.user_groupby = 'partner_id,currency_id,id'

        options = self._generate_options(self.report, '2017-01-01', '2017-12-31')

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,        21200.0,        0.0),
                ('partner_a',                           20000.0,        '',             20150.0),
                ('partner_b',                           1000.0,         '',             1200.0),
                ('partner_c',                           '',             21000.0,        -21350.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('Total Partner Ledger',                21200.0,        21200.0,        0.0),
            ],
            options,
        )

        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.partner_ledger_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,        21200.0,        0.0),
                ('partner_a',                           20000.0,        '',             20150.0),
                ('CAD',                                 '',             '',             50.0),
                ('USD',                                 20000.0,        '',             20100.0),
                ('Total partner_a',                     20000.0,        '',             20150.0),
                ('partner_b',                           1000.0,         '',             1200.0),
                ('partner_c',                           '',             21000.0,        -21350.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('Total Partner Ledger',                21200.0,        21200.0,        0.0),
            ],
            options,
        )

        company2_currency_line_id = self.report._get_generic_line_id(model_name='res.currency', value=self.company_data_2['currency'].id, markup={'groupby': 'currency_id'}, parent_line_id=partner_a_line_id)
        options['unfolded_lines'].append(company2_currency_line_id)

        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,        21200.0,        0.0),
                ('partner_a',                           20000.0,        '',             20150.0),
                ('CAD',                                 '',             '',             50.0),
                ('Initial Balance',                     '',             '',             50.0),
                ('Total CAD',                           '',             '',             50.0),
                ('USD',                                 20000.0,        '',             20100.0),
                ('Total partner_a',                     20000.0,        '',             20150.0),
                ('partner_b',                           1000.0,         '',             1200.0),
                ('partner_c',                           '',             21000.0,        -21350.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('Total Partner Ledger',                21200.0,        21200.0,        0.0),
            ],
            options,
        )

        options = self._generate_options(self.report, '2017-01-01', '2017-12-31', default_options={'unfold_all': True, 'test_unfold_all': True})

        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      21200.0,        21200.0,        0.0),

                ('partner_a',                           20000.0,        '',             20150.0),
                ('CAD',                                 '',             '',             50.0),
                ('Initial Balance',                     '',             '',             50.0),
                ('Total CAD',                           '',             '',             50.0),
                ('USD',                                 20000.0,        '',             20100.0),
                ('Initial Balance',                     '',             '',             100.0),
                ('MISC/2017/01/0001 2017_1_2',          2000.0,         '',             2100.0),
                ('MISC/2017/01/0001 2017_1_3',          3000.0,         '',             5100.0),
                ('MISC/2017/01/0001 2017_1_4',          4000.0,         '',             9100.0),
                ('MISC/2017/01/0001 2017_1_5',          5000.0,         '',             14100.0),
                ('MISC/2017/01/0001 2017_1_6',          6000.0,         '',             20100.0),
                ('Total USD',                           20000.0,        '',             20100.0),
                ('Total partner_a',                     20000.0,        '',             20150.0),

                ('partner_b',                           1000.0,         '',             1200.0),
                ('USD',                                 1000.0,         '',             1200.0),
                ('Initial Balance',                     '',             '',             200.0),
                ('MISC/2017/01/0001 2017_1_1',          1000.0,         '',             1200.0),
                ('Total USD',                           1000.0,         '',             1200.0),
                ('Total partner_b',                     1000.0,         '',             1200.0),

                ('partner_c',                           '',             21000.0,        -21350.0),
                ('CAD',                                 '',             '',             -50.0),
                ('Initial Balance',                     '',             '',             -50.0),
                ('Total CAD',                           '',             '',             -50.0),
                ('USD',                                 '',             21000.0,        -21300.0),
                ('Initial Balance',                     '',             '',             -300.0),
                ('MISC/2017/01/0001 2017_1_7',          '',             6000.0,         -6300.0),
                ('MISC/2017/01/0001 2017_1_8',          '',             7000.0,         -13300.0),
                ('MISC/2017/01/0001 2017_1_9',          '',             8000.0,         -21300.0),
                ('Total USD',                           '',             21000.0,        -21300.0),
                ('Total partner_c',                     '',             21000.0,        -21350.0),

                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('CAD',                                 200.0,          200.0,          0.0),
                ('MISC/2017/06/0001 2017_2_1',          200.0,          '',             200.0),
                ('MISC/2017/06/0001 2017_2_2',          '',             200.0,          0.0),
                ('Total CAD',                           200.0,          200.0,          0.0),
                ('Total Unknown Partner',               200.0,          200.0,          0.0),

                ('Total Partner Ledger',                21200.0,        21200.0,        0.0),
            ],
            options,
        )

    def test_filter_unreconciled_entries_only(self):
        new_partner = self.env['res.partner'].create({'name': 'Obiwan Kenobi'})
        move_1 = self.init_invoice('out_invoice', partner=new_partner, invoice_date='2019-01-01', amounts=[1000.0], taxes=[], post=True)
        move_2 = self.init_invoice('out_invoice', partner=new_partner, invoice_date='2019-01-01', amounts=[5000.0], taxes=[], post=True)

        self.env['account.payment.register'].create({
            'payment_date': '2019-01-01',
            'line_ids': move_1.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            'amount': 700.0,
        })._create_payments()
        self.env['account.payment.register'].create({
            'payment_date': '2019-01-01',
            'line_ids': move_2.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
        })._create_payments()

        self.assertEqual(move_1.payment_state, 'partial')
        self.assertEqual(move_2.payment_state, move_2._get_invoice_in_payment_state())

        options = self._generate_options(self.report, '2019-01-01', '2019-12-31', default_options={'partner_ids': new_partner.ids})
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                      Debit              Credit            Balance
            [   0,                                            6,                  7,                9],
            [
                ('Partner Ledger',                       6000.0,             5700.0,             300.0),
                ('Obiwan Kenobi',                        6000.0,             5700.0,             300.0),
                ('Total Partner Ledger',                 6000.0,             5700.0,             300.0),
            ],
            options
        )

        options = self._generate_options(self.report, '2024-01-01', '2024-12-31', default_options={
            'unreconciled': True,
            'partner_ids': new_partner.ids,
        })

        self.assertEqual(
            options['recon_date'],
            {'date_to': '2024-12-31', 'date_to_str': '12/31/2024'},
        )

        self.assertLinesValues(
            self.report._get_lines(options),
            #              Name                           Balance
            [                0,                                  9],
            [
                ('Partner Ledger',                           300.0),
                ('Obiwan Kenobi',                            300.0),
                ('Total Partner Ledger',                     300.0),
            ],
            options
        )

    def _create_move(self, partner=None, **field_vals):
        partner = partner or self.partner
        return self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2024-10-10',
            'journal_id': self.company_data['default_journal_bank'].id,
            'line_ids': [
                Command.create({'debit': 0.0,       'credit': 500.0,    'account_id': partner.property_account_receivable_id.id, 'partner_id': partner.id}),
                Command.create({'debit': 500.0,     'credit': 0.0,      'account_id': self.company_data['default_journal_bank'].default_account_id.id}),
            ],
            **field_vals,
        })

    def test_reconcile_to_date(self):
        new_partner = self.env['res.partner'].create({'name': 'Obiwan Kenobi'})
        inv = self._create_invoice(partner_id=new_partner, invoice_date='2024-12-30')
        inv_2 = self._create_invoice(partner_id=new_partner, invoice_date='2025-02-07')
        (inv + inv_2)._post()

        part_pay = self._create_move(date='2025-01-10', partner=new_partner)
        part_pay_2 = self._create_move(date='2025-03-10', partner=new_partner)
        final_pay = self._create_move(date='2025-05-10', partner=new_partner, line_ids=[
            Command.create({'debit': 0.0,       'credit': 410.0,    'account_id': new_partner.property_account_receivable_id.id, 'partner_id': new_partner.id}),
            Command.create({'debit': 410.0,     'credit':   0.0,    'account_id': self.company_data['default_journal_bank'].default_account_id.id}),
        ])

        (part_pay + part_pay_2 + final_pay).action_post()

        (part_pay + inv).line_ids.filtered(
            lambda line: line.account_id == self.company_data['default_account_receivable']
        ).reconcile()
        (part_pay_2 + inv).line_ids.filtered(
            lambda line: line.account_id == self.company_data['default_account_receivable']
        ).reconcile()
        lines = (final_pay + inv).line_ids.filtered(
            lambda line: line.account_id == self.company_data['default_account_receivable']
        )
        lines.reconcile()
        self.assertTrue(all(line.full_reconcile_id for line in lines))

        options = self._generate_options(self.report, '2024-01-01', '2024-12-31', default_options={'partner_ids': inv.partner_id.ids})
        self.assertLinesValues(
            self.report._get_lines(options),
            #              Name                              Debit              Credit            Balance
            [                0,                                  6,                  7,                9],
            [
                ('Partner Ledger',                          1410.0,                 '',           1410.0),
                ('Obiwan Kenobi',                           1410.0,                 '',           1410.0),
                ('Total Partner Ledger',                    1410.0,                 '',           1410.0),
            ],
            options,
        )

        # partial payment for inv1 is made
        options = self._generate_options(self.report, '2024-01-01', '2025-01-10', default_options={
            'partner_ids': inv.partner_id.ids,
            'unfold_all': True,
            'unreconciled': True,
        })

        self.assertLinesValues(
            self.report._get_lines(options),
            #             Name                       Debit             Credit           Balance
            [                0,                          6,                 7,                9],
            [
                ('Partner Ledger',                  1410.0,             500.0,            910.0),
                ('Obiwan Kenobi',                   1410.0,             500.0,            910.0),
                (inv.name,                          1410.0,             '',               1410.0),
                (part_pay.name,                     '',                 500.0,            910.00),
                ('Total Obiwan Kenobi',             1410.0,             500.0,            910.0),
                ('Total Partner Ledger',            1410.0,             500.0,            910.0),
            ],
            options,
        )

        options = self._generate_options(self.report, '2025-03-01', '2025-03-10', default_options={
            'partner_ids': inv.partner_id.ids,
            'unfold_all': True,
            'unreconciled': True,
        })
        self.assertLinesValues(
            self.report._get_lines(options),
            #             Name                    Debit          Credit           Balance
            [                0,                      6,               7,                 9],
            [
                ('Partner Ledger',                  '',           500.0,            1820.0),
                ('Obiwan Kenobi',                   '',           500.0,            1820.0),
                ('Initial Balance',                 '',              '',            2320.0),
                (part_pay_2.name,                   '',           500.0,            1820.0),
                ('Total Obiwan Kenobi',             '',           500.0,            1820.0),
                ('Total Partner Ledger',            '',           500.0,            1820.0),
            ],
            options,
        )

        options = self._generate_options(self.report, '2024-01-01', '2025-03-10', default_options={
            'partner_ids': inv.partner_id.ids,
            'unfold_all': True,
            'unreconciled': True,
        })
        self.assertLinesValues(
            self.report._get_lines(options),
            #             Name                       Debit             Credit            Balance
            [                0,                          6,                 7,                9],
            [
                ('Partner Ledger',                  2820.0,            1000.0,           1820.0),
                ('Obiwan Kenobi',                   2820.0,            1000.0,           1820.0),
                (inv.name,                          1410.0,             '',              1410.0),
                (part_pay.name,                     '',                 500.0,           910.00),
                (inv_2.name,                        1410.0,             '',              2320.0),
                (part_pay_2.name,                   '',                 500.0,           1820.0),
                ('Total Obiwan Kenobi',             2820.0,            1000.0,           1820.0),
                ('Total Partner Ledger',            2820.0,            1000.0,           1820.0),
            ],
            options,
        )

        # inv and all payments disappear, only inv 2 remains
        options = self._generate_options(self.report, '2024-01-01', '2025-05-10', default_options={
            'partner_ids': inv.partner_id.ids,
            'unfold_all': True,
            'unreconciled': True,
        })
        self.assertLinesValues(
            self.report._get_lines(options),
            #             Name                      Debit            Credit           Balance
            [                0,                         6,               7,                 9],
            [
                ('Partner Ledger',                 1410.0,              '',            1410.0),
                ('Obiwan Kenobi',                  1410.0,              '',            1410.0),
                (inv_2.name,                       1410.0,              '',            1410.0),
                ('Total Obiwan Kenobi',            1410.0,              '',            1410.0),
                ('Total Partner Ledger',           1410.0,              '',            1410.0),
            ],
            options,
        )

    def test_print_pdf_exclude_partner_with_name_similar_to_another_partner_email(self):
        """
        This test verifies that when printing a PDF report, the report accurately reflects the data displayed on the view
        by excluding partners whose email addresses are similar to other partners' names if the search bar is used to filter out partners.
        """
        partner = self.env['res.partner'].create({'name': 'Great Customer', 'email': 'partner_a@test.com'})
        self.init_invoice('out_invoice', partner=partner, invoice_date='2019-02-14', amounts=[1000.0], taxes=[], post=True)
        options = self._generate_options(self.report, '2019-02-01', '2019-02-28', default_options={
                'filter_search_bar': 'partner_a',
                'export_mode': 'print',
            })
        lines = self.report._get_lines(options)
        self.assertFalse(partner.name in [line.name for line in lines])

    def test_partner_ledger_search_with_unknown_partner(self):
        ''' Test that the lines with no partners are included in the report when searching for "Unknown Partner" '''
        options = self._generate_options(self.report, '2017-01-01', '2017-12-31', default_options={
                'filter_search_bar': 'un',
                'export_mode': 'print',
            })

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      200.0,          200.0,          0.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('Total Partner Ledger',                200.0,          200.0,          0.0),
            ],
            options,
        )

        partner = self.env['res.partner'].create({'name': 'Unexpected Customer'})
        self.init_invoice('out_invoice', partner=partner, invoice_date='2017-02-14', amounts=[1000.0], taxes=[], post=True)

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Debit           Credit          Balance
            [   0,                                      6,              7,              9],
            [
                ('Partner Ledger',                      1200.0,         200.0,          1000.0),
                ('Unexpected Customer',                 1000.0,         '',             1000.0),
                ('Unknown Partner',                     200.0,          200.0,          0.0),
                ('Total Partner Ledger',                1200.0,         200.0,          1000.0),
            ],
            options,
        )

    def test_no_amount_currency_col_in_single_currency(self):
        # In multi-currency, we get the amount_currency column
        self.assertGreater(len(self.env['res.currency'].search([])), 1)
        options = self._generate_options(self.report, '2023-01-01', '2023-12-31')
        self.assertTrue(any(col['expression_label'] == 'amount_currency' for col in options['columns']))

        # Not in single-currency
        self.env['res.currency'].search([('name', '!=', 'USD')]).with_context(force_deactivate=True).active = False
        self.assertEqual(len(self.env['res.currency'].search([])), 1)
        options = self._generate_options(self.report, '2023-01-01', '2023-12-31')
        self.assertFalse(any(col['expression_label'] == 'amount_currency' for col in options['columns']))

    def test_partner_ledger_fully_reconcile_previous_year(self):
        """
        Verify the report's behavior when a partner is fully reconciled and has a zero balance.
        If the partner's balance is zero:
            If the partner has any unreconciled items, display the partner's information in the report.
            If the partner has no unreconciled items but has an initial balance > 0, show the partner.
            If the partner has no unreconciled items and has an initial balance = 0, hide the partner.
        """
        new_partner = self.env['res.partner'].create({'name': 'Anakin Skywalker'})
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': '2019-01-01',
            'partner_id': new_partner.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500.0,
                'tax_ids': [],
            })]
        })
        move.action_post()

        payment_1 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2019-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'partner_id': new_partner.id,
            'line_ids': [
                Command.create({'debit': 0.0,       'credit': 500.0,    'account_id': self.company_data['default_account_receivable'].id}),
                Command.create({'debit': 500.0,     'credit': 0.0,      'account_id': self.company_data['default_journal_bank'].default_account_id.id}),
            ],
        })
        payment_1.action_post()

        options = self._generate_options(self.report, '2020-01-01', '2020-12-31', default_options={'partner_ids': new_partner.ids})
        # Balance is 0 but there are unreconciled entries, so we show the line
        self.assertLinesValues(
            self.report._get_lines(options),
            #                   Name                          Debit              Credit           Balance
            [                     0,                             6,                  7,                9],
            [
                ('Partner Ledger',                               '',                '',               0.0),
                ('Total Partner Ledger',                         '',                '',               0.0),
            ],
            options,
        )

        (payment_1 + move).line_ids.filtered(
            lambda line: line.account_id == self.company_data['default_account_receivable']
        ).reconcile()

        # Balance is still 0 and there is no more unreconciled entries, the partner is hide from the report
        self.assertLinesValues(
            self.report._get_lines(options),
            #        Name                                     Debit              Credit           Balance
            [          0,                                        6,                  7,                9],
            [
                ('Partner Ledger',                               '',                 '',               0.0),
                ('Total Partner Ledger',                         '',                 '',               0.0),
            ],
            options,
        )

    def test_partner_ledger_fully_reconcile_current_year(self):
        new_partner = self.env['res.partner'].create({'name': 'Darth Vader'})
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': '2019-01-01',
            'partner_id': new_partner.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500.0,
                'tax_ids': [],
            })]
        })
        move.action_post()

        payment_1 = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2019-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'partner_id': new_partner.id,
            'line_ids': [
                Command.create({'debit': 0.0,       'credit': 500.0,    'account_id': self.company_data['default_account_receivable'].id}),
                Command.create({'debit': 500.0,     'credit': 0.0,      'account_id': self.company_data['default_journal_bank'].default_account_id.id}),
            ],
        })
        payment_1.action_post()

        options = self._generate_options(self.report, '2019-01-01', '2019-12-31', default_options={'partner_ids': new_partner.ids})
        # Balance is 0 but there are unreconciled entries, so we show the line
        self.assertLinesValues(
            self.report._get_lines(options),
            #              Name                              Debit              Credit            Balance
            [                0,                                  6,                  7,                9],
            [
                ('Partner Ledger',                            500.0,              500.0,              0.0),
                ('Darth Vader',                              500.0,              500.0,              0.0),
                ('Total Partner Ledger',                     500.0,              500.0,              0.0),
            ],
            options,
        )

        (payment_1 + move).line_ids.filtered(
            lambda line: line.account_id == self.company_data['default_account_receivable']
        ).reconcile()

        # Balance is still 0 and there is no more unreconciled entries, but the moves is in the current report period,
        # so we still show the partner in the report
        self.assertLinesValues(
            self.report._get_lines(options),
            #             Name                               Debit              Credit            Balance
            [                0,                                  6,                  7,                9],
            [
                ('Partner Ledger',                           500.0,              500.0,              0.0),
                ('Darth Vader',                              500.0,              500.0,              0.0),
                ('Total Partner Ledger',                     500.0,              500.0,              0.0),
            ],
            options,
        )

    def test_partner_ledger_toggle_followup(self):
        """Make sure that toggling the followup also (and only) toggles other lines of the same invoice."""
        installments_payment_term = self.env['account.payment.term'].create({
            'name': "3 installments",
            'line_ids': [
                Command.create({'value_amount': 40, 'value': 'percent', 'nb_days': 0}),
                Command.create({'value_amount': 30, 'value': 'percent', 'nb_days': 30}),
                Command.create({'value_amount': 30, 'value': 'percent', 'nb_days': 60}),
            ],
        })
        invoices = self.env['account.move'].create([
            {
                'move_type': 'out_invoice',
                'invoice_date': fields.Date.from_string('2024-08-01'),
                'partner_id': self.partner_a.id,
                'invoice_line_ids': [Command.create({'quantity': 1, 'price_unit': 1000})],
                'invoice_payment_term_id': installments_payment_term.id,
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': fields.Date.from_string('2024-08-10'),
                'partner_id': self.partner_a.id,
                'invoice_line_ids': [Command.create({'quantity': 1, 'price_unit': 500})],
                'invoice_payment_term_id': installments_payment_term.id,
            },
        ])
        invoices.action_post()
        invoice_name = invoices[0].name
        options = self._generate_options(self.report, '2024-01-01', '2024-12-31', default_options={'unfold_all': True, 'test_unfold_all': True})
        lines = self.report._get_lines(options)
        line_ids = [line.id for line in lines]
        invoice_1_line_ids = [line.id for line in lines if invoice_name in line.name]
        self.assertEqual(
            self.env['account.partner.ledger.report.handler'].action_toggle_no_followup(invoice_1_line_ids[0], line_ids)['updated_line_ids'],
            invoice_1_line_ids,
        )

    def test_reconciled_misc_without_partner_shows_with_partner_filter(self):
        """A misc move without a partner reconciled with a partner invoice must still appear
        when filtering the Partner Ledger by that partner."""
        bernard = self.env['res.partner'].create({'name': 'Bernard Gagnant'})
        invoice = self.init_invoice('out_invoice', partner=bernard, invoice_date='2019-03-01', amounts=[1000.0], taxes=[], post=True)

        misc_move = self.env['account.move'].create({
            'date': '2019-03-02',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 1000.0, 'credit': 0.0, 'account_id': self.company_data['default_account_revenue'].id}),
                (0, 0, {'debit': 0.0,    'credit': 1000.0, 'account_id': self.company_data['default_account_receivable'].id}),
            ],
        })
        misc_move.action_post()

        invoice_receivable = invoice.line_ids.filtered(lambda l: l.account_id == self.company_data['default_account_receivable'])
        misc_receivable = misc_move.line_ids.filtered(lambda l: l.account_id == self.company_data['default_account_receivable'] and not l.partner_id)
        (invoice_receivable + misc_receivable).reconcile()

        # Ensure both the invoice and the misc move appear when the report is fully unfolded.
        options = self._generate_options(self.report, '2019-03-01', '2019-03-31', default_options={'unfold_all': True, 'test_unfold_all': True})
        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                         6,              7,             9],
            [
                ('Partner Ledger',                    2000.0,         2000.0,           0.0),
                (bernard.name,                        1000.0,         1000.0,           0.0),
                (invoice.name,                        1000.0,             '',        1000.0),
                (misc_move.name,                          '',         1000.0,           0.0),
                ('Total ' + bernard.name,             1000.0,         1000.0,           0.0),
                ('partner_a',                             '',             '',       20150.0),
                ('Initial Balance',                       '',             '',       20150.0),
                ('Total partner_a',                       '',             '',       20150.0),
                ('partner_b',                             '',             '',        1200.0),
                ('Initial Balance',                       '',             '',        1200.0),
                ('Total partner_b',                       '',             '',        1200.0),
                ('partner_c',                             '',             '',      -21350.0),
                ('Initial Balance',                       '',             '',      -21350.0),
                ('Total partner_c',                       '',             '',      -21350.0),
                ('Unknown Partner',                   1000.0,         1000.0,           0.0),
                ('MISC/2019/03/0001',                 1000.0,             '',        1000.0),
                ('MISC/2019/03/0001',                     '',         1000.0,           0.0),
                ('Total Unknown Partner',             1000.0,         1000.0,           0.0),
                ('Total Partner Ledger',              2000.0,         2000.0,           0.0),
            ],
            options,
        )

        # When filtering the report by the partner, the misc move (despite having no partner)
        # must still appear because it is reconciled with the partner's invoice.
        options_partner = self._generate_options(self.report, '2019-03-01', '2019-03-31', default_options={'unfold_all': True, 'test_unfold_all': True, 'partner_ids': bernard.ids})
        lines_filtered = self.report._get_lines(options_partner)
        self.assertLinesValues(
            lines_filtered,
            #   Name                                    Debit           Credit          Balance
            [   0,                                         6,              7,             9],
            [
                ('Partner Ledger',                    1000.0,         1000.0,           0.0),
                (bernard.name,                        1000.0,         1000.0,           0.0),
                (invoice.name,                        1000.0,             '',        1000.0),
                (misc_move.name,                          '',         1000.0,           0.0),
                ('Total ' + bernard.name,             1000.0,         1000.0,           0.0),
                ('Total Partner Ledger',              1000.0,         1000.0,           0.0),
            ],
            options_partner,
        )

    def test_single_currency_totals(self):
        """
        Test that the report displays the total amount in currency
        when all invoices from a partner share the same foreign currency.
        """
        partner_d = self.env['res.partner'].create({'name': 'partner_d'})
        partner_e = self.env['res.partner'].create({'name': 'partner_e'})
        partner_f = self.env['res.partner'].create({'name': 'partner_f'})
        other_currency = self.setup_other_currency('EUR')

        invoice_vals = {
            'move_type': 'out_invoice',
            'invoice_date': '2025-03-10',
            'partner_id': partner_d.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 200,
                'tax_ids': [],
            })]
        }
        options = self._generate_options(self.report, '2025-03-01', '2025-03-31', default_options={
            'partner_ids': [partner_d.id, partner_e.id, partner_f.id]
        })

        unreconciled_options = self._generate_options(self.report, "2025-03-01", "2025-03-31",
            default_options={
                "partner_ids": [partner_d.id, partner_e.id, partner_f.id],
                "unreconciled": True,
            },
        )

        # First unpaid invoice in foreign currency.
        self.env['account.move'].create({**invoice_vals, 'currency_id': other_currency.id}).action_post()

        # Second unpaid invoice using the same foreign currency.
        self.env['account.move'].create({**invoice_vals, 'currency_id': other_currency.id}).action_post()

        self.assertEqual(self.report._get_lines(options), self.report._get_lines(unreconciled_options))
        # The amount currency total should be displayed.
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                 Amount,        Amount Currency
            [   0,                                   9,             8],
            [
                ('Partner Ledger',                   200.0,         400.0),
                ('partner_d',                        200.0,         400.0),
                ('Total Partner Ledger',             200.0,         400.0),
            ],
            options,
            currency_map={8: {'currency': other_currency}},
        )

        # Third unpaid invoice using the company currency.
        self.env['account.move'].create(invoice_vals).action_post()

        # The amount currency total should no longer be displayed.
        self.assertEqual(self.report._get_lines(options), self.report._get_lines(unreconciled_options))
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                 Amount,        Amount Currency
            [   0,                                   9,             8],
            [
                ('Partner Ledger',                   400.0,         ''),
                ('partner_d',                        400.0,         ''),
                ('Total Partner Ledger',             400.0,         ''),
            ],
            options,
        )

        self.env['account.move'].create({**invoice_vals, 'partner_id': partner_e.id}).action_post()

        # The 'amount_currency' column should remain empty for 'partner_e', even though
        # there's only one currency (company currency values should not appear in the 'amount_currency' column).
        self.assertEqual(self.report._get_lines(options), self.report._get_lines(unreconciled_options))
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                 Amount,        Amount Currency
        [   0,                                       9,             8],
            [
                ('Partner Ledger',                   600.0,         ''),
                ('partner_d',                        400.0,         ''),
                ('partner_e',                        200.0,         ''),
                ('Total Partner Ledger',             600.0,         ''),
            ],
            options,
        )
        self.env['account.move'].create({**invoice_vals, 'partner_id': partner_f.id, 'currency_id': other_currency.id}).action_post()

        # The 'amount_currency' column should have a value for 'partner_f', since
        # there's only one currency (currency different than the company currency values should appear in the 'amount_currency' column).
        self.assertEqual(self.report._get_lines(options), self.report._get_lines(unreconciled_options))
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                 Amount,        Amount Currency
            [   0,                                   9,             8],
            [
                ('Partner Ledger',                   700.0,         ''),
                ('partner_d',                        400.0,         ''),
                ('partner_e',                        200.0,         ''),
                ('partner_f',                        100.0,         200.0),
                ('Total Partner Ledger',             700.0,         ''),
            ],
            options,
            currency_map={8: {'currency': other_currency}},
        )
