from datetime import date

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestAustrianAccountReturns(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_chart_template('at')
    def setUpClass(cls):
        super().setUpClass()
        cls.tax_return_type = cls.env.ref('l10n_at_reports.at_tax_return_type')
        cls.ec_sales_list_return_type = cls.env.ref('l10n_at_reports.at_ec_sales_list_return_type')

    def _create_return(self, return_type, date_from, date_to):
        return self.env['account.return'].create({
            'name': 'l10n_at test return',
            'company_id': self.env.company.id,
            'type_id': return_type.id,
            'date_from': date_from,
            'date_to': date_to,
        })

    def test_tax_return_deadline(self):
        self.env.company.account_return_periodicity = 'monthly'
        monthly_return = self._create_return(
            self.tax_return_type,
            date(2026, 1, 1),
            date(2026, 1, 31),
        )
        self.assertEqual(monthly_return.date_deadline, date(2026, 3, 15))

        self.env.company.account_return_periodicity = 'trimester'
        quarterly_return = self._create_return(
            self.tax_return_type,
            date(2026, 1, 1),
            date(2026, 3, 31),
        )
        self.assertEqual(quarterly_return.date_deadline, date(2026, 5, 15))

    def test_ec_sales_list_deadline(self):
        self.env.company.account_return_periodicity = 'monthly'
        monthly_return = self._create_return(
            self.ec_sales_list_return_type,
            date(2026, 1, 1),
            date(2026, 1, 31),
        )
        self.assertEqual(monthly_return.date_deadline, date(2026, 2, 28))

        self.env.company.account_return_periodicity = 'trimester'
        quarterly_return = self._create_return(
            self.ec_sales_list_return_type,
            date(2026, 1, 1),
            date(2026, 3, 31),
        )
        self.assertEqual(quarterly_return.date_deadline, date(2026, 4, 30))
