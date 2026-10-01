# Part of Odoo. See LICENSE file for full copyright and licensing details.
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestNlEcSalesReport(AccountSalesReportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('nl')
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref('l10n_nl_reports.dutch_icp_report')
        cls.env.company.totals_below_sections = False
        cls.company.vat = 'NL123456782B90'
        cls.partner_b.update({
            'country_id': cls.env.ref('base.de').id,
            'vat': "DE123456788",
        })

        cls.goods_tax = cls.env.ref(f'account.{cls.env.company.id}_btw_X0_producten')
        cls.services_tax = cls.env.ref(f'account.{cls.env.company.id}_btw_X0_diensten')
        cls.triangular_tax = cls.env.ref(f'account.{cls.env.company.id}_btw_X0_ABC_levering')

    def _create_invoice_nl(self, invoice_date):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_b.id,
            'invoice_date': invoice_date,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Goods Line',
                    'price_unit': 1799.0,
                    'product_id': self.product_a.id,
                    'quantity': 1.0,
                    'account_id': self.company_data['default_account_revenue'].id,
                    'tax_ids': [Command.set(self.goods_tax.ids)],
                }),
                Command.create({
                    'name': 'Services Line',
                    'price_unit': 200.0,
                    'product_id': False,
                    'quantity': 1.0,
                    'account_id': self.company_data['default_account_revenue'].id,
                    'tax_ids': [Command.set(self.services_tax.ids)],
                }),
                Command.create({
                    'name': 'Triangular Line',
                    'price_unit': 300.0,
                    'product_id': False,
                    'quantity': 1.0,
                    'account_id': self.company_data['default_account_revenue'].id,
                    'tax_ids': [Command.set(self.triangular_tax.ids)],
                }),
            ]
        })
        invoice.action_post()
        return invoice

    @freeze_time('2019-12-31')
    def test_nl_ec_sales_report(self):
        self._create_invoice_nl('2019-12-01')

        options = self.report.get_options({'date': {'default_opening_date': 'this_month'}})
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Line Name                      Goods      Services      Triangular    Total
            [   0,                             3,           4,            5,            6],
            [
                ('EC Sales Report',         1799.0,      200.0,        300.0,        2299.0),
                (self.partner_b.name,       1799.0,      200.0,        300.0,        2299.0),
            ],
            options,
        )
