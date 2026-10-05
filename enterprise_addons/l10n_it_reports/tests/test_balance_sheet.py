from odoo import Command
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nItBalanceSheet(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('it')
    def setUpClass(cls):
        super().setUpClass()

        cls.report = cls.env.ref('l10n_it_reports.account_financial_report_it_sp')

        cls.account_180 = cls._create_test_account('1809999', 'Test account 180')
        cls.account_182 = cls._create_test_account('1829999', 'Test account 182')
        cls.account_183 = cls._create_test_account('1839999', 'Test account 183')
        cls.account_184 = cls._create_test_account('1849999', 'Test account 184')
        cls.account_185 = cls._create_test_account('1859999', 'Test account 185')

    @classmethod
    def _create_test_account(cls, code, name):
        return cls.env['account.account'].with_company(cls.company).create({
            'code': code,
            'name': name,
            'account_type': 'asset_cash',
        })

    def _post_balance(self, account, amount, date='2024-06-30'):
        self.env['account.move'].create({
            'move_type': 'entry',
            'date': date,
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                Command.create({'account_id': account.id, 'debit': amount, 'credit': 0.0}),
                Command.create({'account_id': self.company_data['default_account_revenue'].id, 'debit': 0.0, 'credit': amount}),
            ],
        }).action_post()

    def _get_report_line(self, lines, name):
        matches = [line for line in lines if line.name == name]
        self.assertEqual(len(matches), 1, f"Expected exactly one line named {name!r}, found {len(matches)}")
        return matches[0]

    def test_cash_and_cash_equivalents_account_codes(self):
        self._post_balance(self.account_180, 100.0)
        self._post_balance(self.account_182, 250.0)
        self._post_balance(self.account_183, 60.0)
        self._post_balance(self.account_184, 40.0)
        self._post_balance(self.account_185, 300.0)

        options = self._generate_options(self.report, '2024-01-01', '2024-12-31')
        lines = self.report._get_lines(options)

        bank_and_postal = self._get_report_line(lines, '1. Bank and postal deposits')
        checks = self._get_report_line(lines, '2. Checks')
        cash_box = self._get_report_line(lines, '3. Money and valuables in the cash box')
        cash_and_equivalents = self._get_report_line(lines, 'IV. Cash and cash equivalents')

        self.assertAlmostEqual(bank_and_postal.columns[0].no_format, 310.0)
        self.assertAlmostEqual(checks.columns[0].no_format, 300.0)
        self.assertAlmostEqual(cash_box.columns[0].no_format, 140.0)
        self.assertAlmostEqual(cash_and_equivalents.columns[0].no_format, 750.0)
