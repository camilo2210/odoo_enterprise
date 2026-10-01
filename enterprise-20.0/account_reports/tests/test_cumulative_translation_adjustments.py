from odoo import Command
from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged('post_install', '-at_install')
class TestCTA(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].write({'name': "USD Company", 'sequence': 1, 'totals_below_sections': False})
        cls.company_data_2['company'].write({'name': 'CAD Company', 'sequence': 2, 'totals_below_sections': False})
        cad = cls.env.ref('base.CAD')
        cls.env['res.currency.rate'].search([]).unlink()
        cls.env['res.currency.rate'].create([
            {'name': '2025-01-01', 'rate': 1.1, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.9090909091
            {'name': '2025-02-01', 'rate': 1.2, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.8333333333
            {'name': '2025-03-01', 'rate': 1.3, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.7692307692
            {'name': '2025-04-01', 'rate': 1.4, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.7142857143
            {'name': '2025-05-01', 'rate': 1.5, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.6666666667
            {'name': '2025-06-01', 'rate': 1.6, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.625
            {'name': '2025-07-01', 'rate': 1.7, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.5882352941
            {'name': '2025-08-01', 'rate': 1.8, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.5555555556
            {'name': '2025-09-01', 'rate': 1.9, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.5263157895
            {'name': '2025-10-01', 'rate': 2.0, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.5
            {'name': '2025-11-01', 'rate': 2.1, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.4761904762
            {'name': '2025-12-01', 'rate': 2.2, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.4545454545
            {'name': '2026-01-01', 'rate': 2.3, 'currency_id': cad.id, 'company_id': cls.company_data['company'].id},  # inverse: 0.4347826087
        ])

        current_year_earning_account = cls.company_data_2['company'].get_unaffected_earnings_account()
        equity_account = cls.env['account.account'].search([
            *cls.env['account.account']._check_company_domain(cls.company_data_2['company']),
            ('account_type', '=', 'equity'),
        ], limit=1)

        cls.moves = cls.env['account.move'].with_company(cls.company_data_2['company']).create([{
            'date': '2025-10-10',
            'line_ids': [
                Command.create({
                    'account_id': cls.company_data_2['default_account_expense'].id,
                    'balance': 3000.0,  # average rate 0.633781251663689
                }),
                Command.create({
                    'account_id': cls.company_data_2['default_account_deferred_expense'].id,
                    'balance': 450.0,  # closing rate 0.4545454545
                }),
                Command.create({
                    'account_id': cls.company_data_2['default_account_payable'].id,
                    'balance': -3450.0,  # closing rate 0.4545454545
                }),
            ],
        }, {
            'date': '2025-10-10',
            'line_ids': [
                Command.create({
                    'account_id': cls.company_data_2['default_account_revenue'].id,
                    'balance': -10000.0,  # average rate 0.633781251663689
                }),
                Command.create({
                    'account_id': cls.company_data_2['default_account_deferred_revenue'].id,
                    'balance': -1500.0,  # closing rate 0.4545454545
                }),
                Command.create({
                    'account_id': cls.company_data_2['default_account_receivable'].id,
                    'balance': 11500.0,  # closing rate 0.4545454545
                }),
            ],
        }, {
            'date': '2025-12-31',
            'line_ids': [
                Command.create({
                    'account_id': current_year_earning_account.id,
                    'balance': 6000.0,  # average rate 0.633781251663689
                }),
                Command.create({
                    'account_id': equity_account.id,
                    'balance': -6000.0,  # historic rate 0.4545454545
                }),
            ],
        }, {
            'date': '2025-12-31',
            'line_ids': [
                Command.create({
                    'account_id': current_year_earning_account.id,
                    'balance': 1000.0,  # average rate 0.633781251663689
                }),
                Command.create({
                    'account_id': equity_account.id,
                    'balance': -1000.0,  # historic rate 0.4545454545
                }),
            ],
        }, {
            'date': '2025-06-02',
            'line_ids': [
                Command.create({
                    'account_id': cls.company_data_2['default_journal_bank'].default_account_id.id,
                    'balance': 2000.0,  # closing rate 0.4545454545
                }),
                Command.create({
                    'account_id': equity_account.id,
                    'balance': -2000.0,  # historic rate 0.625
                }),
            ],
        }])
        cls.moves.action_post()

    def test_cta_value(self):
        self.assertRecordValues(self.moves.line_ids.with_context(
            date_from='2025-01-01',
            date_to='2025-12-31',
            allowed_company_ids=[self.company_data['company'].id, self.company_data_2['company'].id],
            currency_translation='cta',
        ), [
            {'consolidation_rate': 0.6337812516636894,    'consolidation_balance':  1901.34, 'cta_value':   537.70},
            {'consolidation_rate': 0.45454545454545453,   'consolidation_balance':   204.55, 'cta_value':     0.00},
            {'consolidation_rate': 0.45454545454545453,   'consolidation_balance': -1568.18, 'cta_value':     0.00},
            {'consolidation_rate': 0.6337812516636894,    'consolidation_balance': -6337.81, 'cta_value': -1792.36},
            {'consolidation_rate': 0.45454545454545453,   'consolidation_balance':  -681.82, 'cta_value':     0.00},
            {'consolidation_rate': 0.45454545454545453,   'consolidation_balance':  5227.27, 'cta_value':     0.00},
            {'consolidation_rate': 0.6337812516636894,    'consolidation_balance':  3802.69, 'cta_value':  1075.42},
            {'consolidation_rate': 0.45454545454545453,   'consolidation_balance': -2727.27, 'cta_value':     0.00},
            {'consolidation_rate': 0.6337812516636894,    'consolidation_balance':   633.78, 'cta_value':   179.23},
            {'consolidation_rate': 0.45454545454545453,   'consolidation_balance':  -454.55, 'cta_value':     0.00},
            {'consolidation_rate': 0.45454545454545453,   'consolidation_balance':   909.09, 'cta_value':     0.00},
            {'consolidation_rate': 0.62500000000000000,   'consolidation_balance': -1250.00, 'cta_value':  -340.91},
        ])

    def test_cta_in_balance_sheet(self):
        report = self.env.ref("account_reports.balance_sheet")
        options = self._generate_options(report, '2025-01-01', '2025-12-31')

        self.assertLinesValues(
            report._get_lines(options),
            #   Name                                            Balance     RATE
            [0, 1],
            [
                ('ASSETS',                                      6340.91),
                ('Current Assets',                              6340.91),
                ('Bank and Cash Accounts',                       909.09),  # closing: 2000 * 0.454545
                ('Receivables',                                 5227.27),  # closing: 11500 * 0.454545
                ('Current Assets',                               204.55),  # closing: 450 * 0.454545
                ('Prepayments',                                    0.00),
                ('Fixed Assets',                                   0.00),
                ('Non-current Assets',                             0.00),

                ('LIABILITIES',                                 2250.00),
                ('Current Liabilities',                         2250.00),
                ('Current Liabilities',                          681.82),  # closing: 1500 * 0.454545
                ('Credit Card',                                    0.00),
                ('Payables',                                    1568.18),  # closing: 3450 * 0.454545
                ('Non-current Liabilities',                        0.00),

                ('EQUITY (& EARNINGS)',                         4090.91),
                ('Equity',                                      4431.82),  # historical: 6000 * 0.454545 + 1000 * 0.454545 + 2000 * 0.625000
                ('Earnings',                                       0.00),
                ('Current Year Unallocated Earnings',              0.00),
                ('Previous Years Earnings',                        0.00),
                ('Other Comprehensive Income',                  -340.91),
                ('Cumulative Translation Adjustments',          -340.91),
                ('LIABILITIES + EQUITY',                        6340.91),
            ],
            options,
        )

        options = self._generate_options(report, '2025-01-01', '2025-10-31')
        # Average rate for period 1/1/25 --> 31/10/25 = 0.66766103075
        self.assertLinesValues(
            report._get_lines(options),
            #   Name                                            Balance     RATE
            [0, 1],
            [
                ('ASSETS',                                      6975.00),
                ('Current Assets',                              6975.00),
                ('Bank and Cash Accounts',                      1000.00),  # closing: 2000 * 0.5
                ('Receivables',                                 5750.00),  # closing: 11500 * 0.5
                ('Current Assets',                               225.00),  # closing: 450 * 0.5
                ('Prepayments',                                    0.00),
                ('Fixed Assets',                                   0.00),
                ('Non-current Assets',                             0.00),

                ('LIABILITIES',                                 2475.00),
                ('Current Liabilities',                         2475.00),
                ('Current Liabilities',                          750.00),  # closing: 1500 * 0.5
                ('Credit Card',                                    0.00),
                ('Payables',                                    1725.00),  # closing: 3450 * 0.5
                ('Non-current Liabilities',                        0.00),

                ('EQUITY (& EARNINGS)',                         4500.00),
                ('Equity',                                      1250.00),  # historical: 2000 * 0.625000
                ('Earnings',                                    4673.27),
                ('Current Year Unallocated Earnings',           4673.27),
                ('Previous Years Earnings',                        0.00),
                ('Other Comprehensive Income',                 -1423.27),
                ('Cumulative Translation Adjustments',         -1423.27),
                ('LIABILITIES + EQUITY',                        6975.00),
            ],
            options,
        )

    def test_cta_in_trial_balance(self):
        report = self.env.ref("account_reports.trial_balance_report")
        options = self._generate_options(report, '2025-01-01', '2025-12-31')

        self.assertLinesValues(
            report._get_lines(options),
            #    Name                                      Initial Balance        Debit        Credit      End Balance
            [0,                                                  1,           2,            3,               4],
            [
                ('Bank',                                               0.0,      909.09,          0.0,          909.09),
                ('Current Assets',                                     0.0,      204.55,          0.0,          204.55),
                ('Accounts Receivable',                                0.0,     5227.27,          0.0,         5227.27),
                ('Capital',                                            0.0,         0.0,      4431.82,        -4431.82),
                ('Accumulated Retained Earnings',                      0.0,     4436.47,          0.0,         4436.47),
                ('Expenses',                                           0.0,     1901.34,          0.0,         1901.34),
                ('Product Sales',                                      0.0,         0.0,      6337.81,        -6337.81),
                ('Current Liabilities',                                0.0,         0.0,       681.82,         -681.82),
                ('Accounts Payable',                                   0.0,         0.0,      1568.18,        -1568.18),
                ('Cumulative Translation Adjustments',                 0.0,      340.91,          0.0,          340.91),
                ('Total',                                              0.0,    13019.63,     13019.63,             0.0),
            ],
            options,
        )

    def test_cta_in_general_ledger(self):
        report = self.env.ref("account_reports.general_ledger_report")
        options = self._generate_options(report, '2025-01-01', '2025-12-31')

        self.assertLinesValues(
            report._get_lines(options),
            #    Name                                            Debit        Credit          Balance
            [0,                                              4,            5,               6],
            [
                ('Bank',                                        909.09,          0.0,          909.09),
                ('Current Assets',                              204.55,          0.0,          204.55),
                ('Accounts Receivable',                        5227.27,          0.0,         5227.27),
                ('Capital',                                        0.0,      4431.82,        -4431.82),
                ('Accumulated Retained Earnings',              4436.47,          0.0,         4436.47),
                ('Expenses',                                   1901.34,          0.0,         1901.34),
                ('Product Sales',                                  0.0,      6337.81,        -6337.81),
                ('Current Liabilities',                            0.0,       681.82,         -681.82),
                ('Accounts Payable',                               0.0,      1568.18,        -1568.18),
                ('Cumulative Translation Adjustments',          340.91,          0.0,          340.91),
                ('Total General Ledger',                      13019.63,     13019.63,             0.0),
            ],
            options,
        )
