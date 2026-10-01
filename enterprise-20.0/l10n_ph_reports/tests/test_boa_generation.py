# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io

from dateutil.relativedelta import relativedelta
from odoo import Command, fields
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.l10n_ph.tests.common import TestPhCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_ph_boa_reports")
class TestPhBoaReports(TestAccountReportsCommon, TestPhCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def _create_inv(cls, move_type, date, partner, lines=None, invoice_line_ids=None, **kwargs):
        return cls._create_invoice(
            invoice_line_ids=invoice_line_ids or (lines and [
                Command.create({"name": "Product", "price_unit": amt, "tax_ids": [Command.set(tax.ids)]})
                for amt, tax in lines
            ]),
            post=True,
            move_type=move_type,
            date=date,
            partner_id=partner,
            **kwargs
        )

    @classmethod
    @TestAccountReportsCommon.setup_country("ph")
    def setUpClass(cls):
        super().setUpClass()

        cls.currency_symbol = cls.env.company.currency_id.symbol
        cls.d_fmt = f"\xa0{cls.currency_symbol}"

        ChartTemplate = cls.env["account.chart.template"].with_company(cls.company_data["company"])
        cls.tax_sale_12 = ChartTemplate.ref("l10n_ph_tax_sale_12")
        cls.tax_sale_inc = cls.tax_sale_12.copy({"name": "12% Incl", "price_include_override": "tax_included"})
        cls.tax_purc_12 = ChartTemplate.ref("l10n_ph_tax_purchase_12")
        cls.tax_purc_inc = cls.tax_purc_12.copy({"name": "12% Incl", "price_include_override": "tax_included"})

        cls.partner_local = cls.env["res.partner"].create({"name": "Local Customer", "vat": "123-456-789-000", "street": "123 Rizal Ave", "city": "Manila"})
        cls.partner_us = cls.env["res.partner"].create({"name": "US Vendor", "country_id": cls.env.ref("base.us").id, "vat": "999-000-000"})

        cls.currency_usd = cls.setup_other_currency("USD", rates=[("2015-01-01", 1 / 50), ("2015-02-01", 1 / 60)])

        cls._create_inv("out_invoice", "2025-01-15", cls.partner_local, [(1000.0, cls.tax_sale_12)])
        cls._create_inv("out_invoice", "2025-01-16", cls.partner_local, [(1000.0, cls.tax_sale_inc)])
        cls._create_inv("in_invoice", "2025-01-20", cls.partner_local, [(1000.0, cls.tax_purc_12)])
        cls._create_inv("in_invoice", "2025-01-21", cls.partner_local, [(1000.0, cls.tax_purc_inc)])
        cls._create_inv(
            "in_invoice", "2025-01-15", cls.partner_us, [(100.0, cls.tax_purc_12)],
            currency_id=cls.currency_usd.id,
            invoice_currency_rate=1 / 55
        )
        bill_split = cls._create_invoice(
            "in_invoice", "2025-01-19", partner_id=cls.partner_local, post=False,
            invoice_line_ids=[
                Command.create({"name": n, "price_unit": 1000.0, "tax_ids": [Command.set(cls.tax_purc_12.ids)]})
                for n in ["Item A", "Item B", "Item C"]
            ]
        )
        bill_split.line_ids.filtered(lambda l: l.display_type == "tax").write({"amount_currency": 360.02, "balance": 360.02})
        bill_split.action_post()

    # =========================================================
    # HELPERS
    # =========================================================

    def _get_csv_rows(self, report, options):
        handler = self.env[report.custom_handler_model_name]
        export_data = handler.print_report_to_csv(options)
        return list(csv.reader(io.StringIO(export_data["file_content"].decode("utf-8")), delimiter=","))

    # =========================================================
    # MOVE REPORTS (SALES & PURCHASE)
    # =========================================================

    def test_sales_journal_csv_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_sales_report")
        options = self._generate_options(report, "2025-01-15", "2025-01-21", {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        self.assertEqual(rows, [
            # Date,        VAT,                 Name,                Address,                  Product,     Gross,     Disc,     Tax,      Net
            ["01/15/2025", "123-456-789-000",   "Local Customer",    "123 Rizal Ave, Manila",  "Product",   "1120.00", "0.00",   "120.00", "1000.00"],
            ["01/16/2025", "123-456-789-000",   "Local Customer",    "123 Rizal Ave, Manila",  "Product",   "1000.00", "0.00",   "107.14",  "892.86"],
        ])

    def test_purchase_journal_csv_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_purchases_report")
        options = self._generate_options(report, "2025-01-15", "2025-01-21", {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        self.assertListEqual(rows, [
            # Date,        VAT,                 Name,                Address,                  Product,     Gross,     Disc,     Tax,       Net
            ["01/20/2025", "123-456-789-000",   "Local Customer",    "123 Rizal Ave, Manila",  "Product",   "1120.00", "0.00",   "-120.00", "-1000.00"],
            ["01/21/2025", "123-456-789-000",   "Local Customer",    "123 Rizal Ave, Manila",  "Product",   "1000.00", "0.00",   "-107.14",  "-892.86"],
            ["01/15/2025", "999-000-000",       "US Vendor",         "",                       "Product",   "6160.00", "0.00",   "-660.00", "-5500.00"],
            ["01/19/2025", "123-456-789-000",   "Local Customer",    "123 Rizal Ave, Manila",  "Item A",    "1120.00", "0.00",   "-120.01", "-1000.00"],
            ["01/19/2025", "123-456-789-000",   "Local Customer",    "123 Rizal Ave, Manila",  "Item B",    "1120.00", "0.00",   "-120.00", "-1000.00"],
            ["01/19/2025", "123-456-789-000",   "Local Customer",    "123 Rizal Ave, Manila",  "Item C",    "1120.00", "0.00",   "-120.01", "-1000.00"],
        ])

    # =========================================================
    # GENERAL LEDGER
    # =========================================================

    def test_general_ledger_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_general_ledger_report")
        options = self._generate_options(report, "2025-01-01", "2025-01-31", {"unfold_all": True})
        self.assertLinesValues(
            report._get_lines(options),
            #     Name,                               Date,              Debit,     Credit,      Balance
            [     0,                                  1,                 2,         3,           4],
            [
                ["General Ledger Report",             "",                 13760.02,  13760.02,         0.00],
                [ "103010 Accounts Receivable - Trade", "",                  2120.00,      0.00,      2120.00],
                [  "INV/2025/00001",                  "01/15/2025",        1120.00,      0.00,      1120.00],
                [  "INV/2025/00002",                  "01/16/2025",        1000.00,      0.00,      2120.00],
                [ "Total 103010 Accounts Receivable - Trade", "",          2120.00,      0.00,      2120.00],
                [ "106010 Input VAT 12%",             "",                  1247.16,      0.00,      1247.16],
                [  "BILL/2025/01/0003 12%",           "01/15/2025",         660.00,      0.00,       660.00],
                [  "BILL/2025/01/0004 12%",           "01/19/2025",         360.02,      0.00,      1020.02],
                [  "BILL/2025/01/0001 12%",           "01/20/2025",         120.00,      0.00,      1140.02],
                [  "BILL/2025/01/0002 12% Incl",      "01/21/2025",         107.14,      0.00,      1247.16],
                [ "Total 106010 Input VAT 12%",       "",                  1247.16,      0.00,      1247.16],
                [ "201010 Accounts Payable - Trade",  "",                     0.00,  11640.02,    -11640.02],
                [  "BILL/2025/01/0003",               "01/15/2025",           0.00,   6160.00,     -6160.00],
                [  "BILL/2025/01/0004",               "01/19/2025",           0.00,   3360.02,     -9520.02],
                [  "BILL/2025/01/0001",               "01/20/2025",           0.00,   1120.00,    -10640.02],
                [  "BILL/2025/01/0002",               "01/21/2025",           0.00,   1000.00,    -11640.02],
                [ "Total 201010 Accounts Payable - Trade", "",               0.00,  11640.02,    -11640.02],
                [ "206010 Output VAT 12%",            "",                     0.00,    227.14,      -227.14],
                [  "INV/2025/00001 12%",              "01/15/2025",           0.00,    120.00,      -120.00],
                [  "INV/2025/00002 12% Incl",         "01/16/2025",           0.00,    107.14,      -227.14],
                [ "Total 206010 Output VAT 12%",      "",                     0.00,    227.14,      -227.14],
                [ "401010 Sales/Revenues",             "",                     0.00,   1892.86,     -1892.86],
                [  "INV/2025/00001 Product",          "01/15/2025",           0.00,   1000.00,     -1000.00],
                [  "INV/2025/00002 Product",          "01/16/2025",           0.00,    892.86,     -1892.86],
                [ "Total 401010 Sales/Revenues",       "",                     0.00,   1892.86,     -1892.86],
                [ "603090 Miscellaneous Expenses",    "",                 10392.86,      0.00,     10392.86],
                [  "BILL/2025/01/0003 Product",       "01/15/2025",        5500.00,      0.00,      5500.00],
                [  "BILL/2025/01/0004 Item A",        "01/19/2025",        1000.00,      0.00,      6500.00],
                [  "BILL/2025/01/0004 Item B",        "01/19/2025",        1000.00,      0.00,      7500.00],
                [  "BILL/2025/01/0004 Item C",        "01/19/2025",        1000.00,      0.00,      8500.00],
                [  "BILL/2025/01/0001 Product",       "01/20/2025",        1000.00,      0.00,      9500.00],
                [  "BILL/2025/01/0002 Product",       "01/21/2025",         892.86,      0.00,     10392.86],
                [ "Total 603090 Miscellaneous Expenses", "",               10392.86,      0.00,     10392.86],
                ["Total General Ledger Report",       "",                 13760.02,  13760.02,         0.00],
            ],
            options,
        )

    def test_general_ledger_csv_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_general_ledger_report")
        options = self._generate_options(report, "2025-01-01", "2025-01-31", {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        self.assertEqual(rows, [
            # Acc Code,  Account Name,           Reference/Label,                 Date,            Debit,      Credit,      Balance
            ["103010",  "Accounts Receivable - Trade", "INV/2025/00001",          "01/15/2025",  "1120.00",     "0.00",    "1120.00"],
            ["103010",  "Accounts Receivable - Trade", "INV/2025/00002",          "01/16/2025",  "1000.00",     "0.00",    "2120.00"],
            ["106010",  "Input VAT 12%",               "BILL/2025/01/0003 12%",   "01/15/2025",   "660.00",     "0.00",     "660.00"],
            ["106010",  "Input VAT 12%",               "BILL/2025/01/0004 12%",   "01/19/2025",   "360.02",     "0.00",    "1020.02"],
            ["106010",  "Input VAT 12%",               "BILL/2025/01/0001 12%",   "01/20/2025",   "120.00",     "0.00",    "1140.02"],
            ["106010",  "Input VAT 12%",               "BILL/2025/01/0002 12% Incl", "01/21/2025", "107.14",     "0.00",    "1247.16"],
            ["201010",  "Accounts Payable - Trade",    "BILL/2025/01/0003",       "01/15/2025",     "0.00",  "6160.00",   "-6160.00"],
            ["201010",  "Accounts Payable - Trade",    "BILL/2025/01/0004",       "01/19/2025",     "0.00",  "3360.02",   "-9520.02"],
            ["201010",  "Accounts Payable - Trade",    "BILL/2025/01/0001",       "01/20/2025",     "0.00",  "1120.00",   "-10640.02"],
            ["201010",  "Accounts Payable - Trade",    "BILL/2025/01/0002",       "01/21/2025",     "0.00",  "1000.00",   "-11640.02"],
            ["206010",  "Output VAT 12%",              "INV/2025/00001 12%",      "01/15/2025",     "0.00",   "120.00",    "-120.00"],
            ["206010",  "Output VAT 12%",              "INV/2025/00002 12% Incl", "01/16/2025",     "0.00",   "107.14",    "-227.14"],
            ["401010",  "Sales/Revenues",               "INV/2025/00001 Product",  "01/15/2025",     "0.00",  "1000.00",   "-1000.00"],
            ["401010",  "Sales/Revenues",               "INV/2025/00002 Product",  "01/16/2025",     "0.00",   "892.86",   "-1892.86"],
            ["603090",  "Miscellaneous Expenses",      "BILL/2025/01/0003 Product", "01/15/2025", "5500.00",     "0.00",    "5500.00"],
            ["603090",  "Miscellaneous Expenses",      "BILL/2025/01/0004 Item A",  "01/19/2025", "1000.00",     "0.00",    "6500.00"],
            ["603090",  "Miscellaneous Expenses",      "BILL/2025/01/0004 Item B",  "01/19/2025", "1000.00",     "0.00",    "7500.00"],
            ["603090",  "Miscellaneous Expenses",      "BILL/2025/01/0004 Item C",  "01/19/2025", "1000.00",     "0.00",    "8500.00"],
            ["603090",  "Miscellaneous Expenses",      "BILL/2025/01/0001 Product", "01/20/2025", "1000.00",     "0.00",    "9500.00"],
            ["603090",  "Miscellaneous Expenses",      "BILL/2025/01/0002 Product", "01/21/2025",  "892.86",     "0.00",   "10392.86"]
        ])

    # =========================================================
    # GENERAL JOURNAL
    # =========================================================

    def test_general_journal_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_general_journal_report")
        options = self._generate_options(report, "2025-01-15", "2025-01-20", {"unfold_all": True})
        self.assertLinesValues(
            report._get_lines(options),
            #    Name,                           Date,         Code,     Account Name,         Debit,    Credit
            [     0,                              1,            2,        3,                    4,        5],
            [
                ["General Journal Report",       "",           "",       "",                    12760.02, 12760.02],
                [ "BILL/2025/01/0001",           "01/20/2025", "",       "",                     1120.00,  1120.00],
                [  "Product",                    "",           "603090", "Miscellaneous Expenses", 1000.00,     0.00],
                [  "12%",                        "",           "106010", "Input VAT 12%",         120.00,     0.00],
                [  "",                           "",           "201010", "Accounts Payable - Trade", 0.00,  1120.00],
                [ "Total BILL/2025/01/0001",     "01/20/2025", "",       "",                     1120.00,  1120.00],
                [ "BILL/2025/01/0003",           "01/15/2025", "",       "",                     6160.00,  6160.00],
                [  "Product",                    "",           "603090", "Miscellaneous Expenses", 5500.00,     0.00],
                [  "12%",                        "",           "106010", "Input VAT 12%",         660.00,     0.00],
                [  "",                           "",           "201010", "Accounts Payable - Trade", 0.00,  6160.00],
                [ "Total BILL/2025/01/0003",     "01/15/2025", "",       "",                     6160.00,  6160.00],
                [ "BILL/2025/01/0004",           "01/19/2025", "",       "",                     3360.02,  3360.02],
                [  "Item A",                     "",           "603090", "Miscellaneous Expenses", 1000.00,     0.00],
                [  "Item B",                     "",           "603090", "Miscellaneous Expenses", 1000.00,     0.00],
                [  "Item C",                     "",           "603090", "Miscellaneous Expenses", 1000.00,     0.00],
                [  "12%",                        "",           "106010", "Input VAT 12%",         360.02,     0.00],
                [  "",                           "",           "201010", "Accounts Payable - Trade", 0.00,  3360.02],
                [ "Total BILL/2025/01/0004",     "01/19/2025", "",       "",                     3360.02,  3360.02],
                [ "INV/2025/00001",              "01/15/2025", "",       "",                     1120.00,  1120.00],
                [  "Product",                    "",           "401010", "Sales/Revenues",           0.00,  1000.00],
                [  "12%",                        "",           "206010", "Output VAT 12%",          0.00,   120.00],
                [  "INV/2025/00001",             "",           "103010", "Accounts Receivable - Trade", 1120.00, 0.00],
                [ "Total INV/2025/00001",        "01/15/2025", "",       "",                     1120.00,  1120.00],
                [ "INV/2025/00002",              "01/16/2025", "",       "",                     1000.00,  1000.00],
                [  "Product",                    "",           "401010", "Sales/Revenues",           0.00,   892.86],
                [  "12% Incl",                   "",           "206010", "Output VAT 12%",          0.00,   107.14],
                [  "INV/2025/00002",             "",           "103010", "Accounts Receivable - Trade", 1000.00, 0.00],
                [ "Total INV/2025/00002",        "01/16/2025", "",       "",                     1000.00,  1000.00],
                ["Total General Journal Report", "",           "",       "",                    12760.02, 12760.02],
            ],
            options,
            ignore_folded=False,
        )

    def test_general_journal_csv_snapshot(self):
        report = self.env.ref("l10n_ph_reports.boa_general_journal_report")
        options = self._generate_options(report, "2025-01-15", "2025-01-20", {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        self.assertEqual(rows, [
            # (account.move) Name/Desc,          Date,         Code,     Account Name,          Debit,        Credit
            ["BILL/2025/01/0001 Product",       "2025-01-20", "603090", "Miscellaneous Expenses", "1000.00",    "0.00"],
            ["BILL/2025/01/0001 12%",           "2025-01-20", "106010", "Input VAT 12%",          "120.00",    "0.00"],
            ["BILL/2025/01/0001",               "2025-01-20", "201010", "Accounts Payable - Trade", "0.00", "1120.00"],
            ["BILL/2025/01/0003 Product",       "2025-01-15", "603090", "Miscellaneous Expenses", "5500.00",    "0.00"],
            ["BILL/2025/01/0003 12%",           "2025-01-15", "106010", "Input VAT 12%",          "660.00",    "0.00"],
            ["BILL/2025/01/0003",               "2025-01-15", "201010", "Accounts Payable - Trade", "0.00", "6160.00"],
            ["BILL/2025/01/0004 Item A",        "2025-01-19", "603090", "Miscellaneous Expenses", "1000.00",    "0.00"],
            ["BILL/2025/01/0004 Item B",        "2025-01-19", "603090", "Miscellaneous Expenses", "1000.00",    "0.00"],
            ["BILL/2025/01/0004 Item C",        "2025-01-19", "603090", "Miscellaneous Expenses", "1000.00",    "0.00"],
            ["BILL/2025/01/0004 12%",           "2025-01-19", "106010", "Input VAT 12%",          "360.02",    "0.00"],
            ["BILL/2025/01/0004",               "2025-01-19", "201010", "Accounts Payable - Trade", "0.00", "3360.02"],
            ["INV/2025/00001 Product",          "2025-01-15", "401010", "Sales/Revenues",            "0.00", "1000.00"],
            ["INV/2025/00001 12%",              "2025-01-15", "206010", "Output VAT 12%",           "0.00",  "120.00"],
            ["INV/2025/00001 INV/2025/00001",   "2025-01-15", "103010", "Accounts Receivable - Trade", "1120.00", "0.00"],
            ["INV/2025/00002 Product",          "2025-01-16", "401010", "Sales/Revenues",            "0.00",  "892.86"],
            ["INV/2025/00002 12% Incl",         "2025-01-16", "206010", "Output VAT 12%",           "0.00",  "107.14"],
            ["INV/2025/00002 INV/2025/00002",   "2025-01-16", "103010", "Accounts Receivable - Trade", "1000.00", "0.00"]
        ])

    # =========================================================
    # AGED PARTNER BALANCE
    # =========================================================

    def _test_aged_partner_balance_csv(self, report_xml_id, move_type, partner, tax):
        report_date = fields.Date.from_string("2025-02-01")

        def iso_date(days_ago):
            return fields.Date.to_string(report_date - relativedelta(days=days_ago))

        def csv_date(days_ago):
            return (report_date - relativedelta(days=days_ago)).strftime("%m/%d/%Y")

        self._create_inv(
            move_type,
            iso_date(0),
            partner,
            invoice_date_due=iso_date(0),
            name="INV/P0",
            invoice_line_ids=[
                Command.create({"name": "Product", "price_unit": 50, "tax_ids": [Command.set(tax.ids)], "date_maturity": iso_date(0)}),
            ],
        )
        self._create_inv(move_type, iso_date(15), partner, [(100.0, tax)], invoice_date_due=iso_date(15), name="INV/P1")
        self._create_inv(move_type, iso_date(45), partner, [(200.0, tax)], invoice_date_due=iso_date(45), name="INV/P2")
        self._create_inv(move_type, iso_date(75), partner, [(300.0, tax)], invoice_date_due=iso_date(75), name="INV/P3")
        self._create_inv(move_type, iso_date(105), partner, [(400.0, tax)], invoice_date_due=iso_date(105), name="INV/P4")
        self._create_inv(move_type, iso_date(135), partner, [(500.0, tax)], invoice_date_due=iso_date(135), name="INV/P5")

        report = self.env.ref(report_xml_id)
        options = self._generate_options(report, report_date, report_date, {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        rows = [r for r in rows if r[0].startswith("INV/P")]
        self.assertEqual(rows, [
            # Name     Date           Not Due  1-30      31-60     61-90     91-120    >120
            ["INV/P0", csv_date(0),   "56.00", "0.00",   "0.00",   "0.00",   "0.00",   "0.00"],
            ["INV/P1", csv_date(15),  "0.00",  "112.00", "0.00",   "0.00",   "0.00",   "0.00"],
            ["INV/P2", csv_date(45),  "0.00",  "0.00",   "224.00", "0.00",   "0.00",   "0.00"],
            ["INV/P3", csv_date(75),  "0.00",  "0.00",   "0.00",   "336.00", "0.00",   "0.00"],
            ["INV/P4", csv_date(105), "0.00",  "0.00",   "0.00",   "0.00",   "448.00", "0.00"],
            ["INV/P5", csv_date(135), "0.00",  "0.00",   "0.00",   "0.00",   "0.00",   "560.00"],
        ])

    def test_aged_receivable_csv_snapshot(self):
        self._test_aged_partner_balance_csv(
            "l10n_ph_reports.boa_aged_receivable_report",
            "out_invoice",
            self.partner_local,
            self.tax_sale_12
        )

    def test_aged_payable_csv_snapshot(self):
        self._test_aged_partner_balance_csv(
            "l10n_ph_reports.boa_aged_payable_report",
            "in_invoice",
            self.partner_local,
            self.tax_purc_12
        )
