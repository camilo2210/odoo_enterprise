# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.l10n_ph_reports.tests.test_boa_generation import TestPhBoaReports
from odoo.addons.stock.tests.common import TestStockCommon
from odoo.fields import Date
from odoo.tests import tagged
from odoo.tools.date_utils import end_of


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_ph_boa_reports")
class TestPhBoaInventory(TestStockCommon, TestPhBoaReports):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.month_end = end_of(Date.today(), "month")

        cls.productA.write({
            "default_code": "NOSTOCK",
            "standard_price": 100.0,
        })
        cls.kgB.write({
            "default_code": "WID-002",
            "standard_price": 500.0,
        })
        cls.productC.write({
            "default_code": False,
            "standard_price": 50.0,
        })
        cls.productD.write({
            "default_code": False,
            "standard_price": 0.0,
        })
        cls.product_template_sofa.write({"is_storable": True})

        quant = cls.env["stock.quant"]
        location_id = cls.warehouse_1.lot_stock_id.id
        quant.create({"product_id": cls.productA.id, "location_id": location_id, "inventory_quantity": 0.0}).action_apply_inventory()
        quant.create({"product_id": cls.kgB.id, "location_id": location_id, "inventory_quantity": 2.0}).action_apply_inventory()
        quant.create({"product_id": cls.productC.id, "location_id": location_id, "inventory_quantity": 10.0}).action_apply_inventory()
        quant.create({"product_id": cls.productD.id, "location_id": location_id, "inventory_quantity": 10.0}).action_apply_inventory()
        quant.create({"product_id": cls.product_sofa_red.id, "location_id": location_id, "inventory_quantity": 5.0}).action_apply_inventory()

    def test_inventory_snapshot(self):
        report = self.env.ref("l10n_ph_reports_stock.boa_inventory_report")
        options = self._generate_options(report, "", self.month_end, {"unfold_all": True})
        lines = report._get_lines(options)
        self.assertLinesValues(
            lines[1:],  # skip the Root
            #    Name,           Code,     Qty,   UoM,     Cost,   Value
            [    0,              1,        2,     3,       4,      5],
            [
                ["kg-B",        "WID-002",  2.0,  "kg",    500.0, 1000.0],
                ["Product C",   "",        10.0, "Units",   50.0,  500.0],
                ["Product D",   "",        10.0, "Units",    0.0,    0.0],
                ["Sofa (red)",  "",         5.0, "Units",    0.0,    0.0],
            ],
            options=options,
        )

    def test_inventory_csv_snapshot(self):
        """This also covers:
        1. Default filter 'Hide Out of Stock',
        2. Variants naming correctly.
        """
        report = self.env.ref("l10n_ph_reports_stock.boa_inventory_report")
        options = self._generate_options(report, "", self.month_end, {"unfold_all": True})
        rows = self._get_csv_rows(report, options)
        date = self.month_end.strftime("%Y-%m-%d")
        self.assertEqual(rows, [
            # Date,  Name,          Code,        Qty,       UoM,        Cost,       Value
            [date,   "kg-B",        "WID-002",    "2.00",   "kg",       "500.00",   "1000.00"],
            [date,   "Product C",   "",          "10.00",   "Units",     "50.00",    "500.00"],
            [date,   "Product D",   "",          "10.00",   "Units",      "0.00",      "0.00"],
            [date,   "Sofa (red)",  "",           "5.00",   "Units",      "0.00",      "0.00"],
        ])

    def test_inventory_report_filter_no_stock(self):
        """Ensure that disabling 'filter_no_stock' reveals products with 0 qty."""
        report = self.env.ref("l10n_ph_reports_stock.boa_inventory_report")
        options = self._generate_options(report, "", self.month_end, {"unfold_all": True, "filter_no_stock": False})
        rows = self._get_csv_rows(report, options)
        self.assertIn("NOSTOCK", [row[2] for row in rows])
