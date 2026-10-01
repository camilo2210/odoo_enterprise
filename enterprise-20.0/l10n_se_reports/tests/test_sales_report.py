# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# pylint: disable=C0326
from freezegun import freeze_time

from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class SwedishSalesReportTest(AccountSalesReportCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountSalesReportCommon.setup_country('se')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.vat = 'SE123456789701'

    @freeze_time('2019-12-31')
    def test_se_ec_sales_report(self):
        goods_tax = self.env.ref(f"account.{self.company_data['company'].id}_sale_tax_goods_EC")
        triangular_tax = self.env.ref(f"account.{self.company_data['company'].id}_triangular_tax_0_goods")
        services_tax = self.env.ref(f"account.{self.company_data['company'].id}_sale_tax_services_EC")

        self._create_invoices([
            (self.partner_a, goods_tax, 3000.3),
            (self.partner_a, goods_tax, 3000.4),
            (self.partner_a, services_tax, 7000.2),
            (self.partner_b, services_tax, 4000.43),
            (self.partner_b, triangular_tax, 2000.12),
        ])
        report = self.env.ref('l10n_se_reports.swedish_ec_sales_report')
        options = report.get_options({'date': {'default_opening_date': 'this_month'}})
        lines = report._get_lines(options)
        self.assertLinesValues(
            # pylint: disable=bad-whitespace
            lines,
            #   Partner                 VAT Number,            Goods,      Triangular,   Services,
            [   0,                      1,                          2,          3,             4],
            [
                ('EC Sales Report',     '',                    6000.70,     2000.12,       11000.63),
                (self.partner_a.name,   self.partner_a.vat,    6000.70,         0.0,        7000.20),
                (self.partner_b.name,   self.partner_b.vat,        0.0,     2000.12,        4000.43),
            ],
            options,
        )
        correct_report = (
            'SKV574008\r\n'
            'SE123456789701;1912;Because I am accountman!;;accountman@test.com;\r\n'
            'FR23334175221;6001;;7000\r\n'
            'BE0477472701;;2000;4000\r\n'
        )
        gen_report = self.env[report.custom_handler_model_name].export_sales_report_to_kvr(options)['file_content'].decode()
        self.assertEqual(gen_report, correct_report, "Error creating KVR")
