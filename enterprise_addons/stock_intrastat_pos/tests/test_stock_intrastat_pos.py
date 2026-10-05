from freezegun import freeze_time

from odoo.tests import tagged

from odoo.addons.stock_intrastat.tests.common import TestStockIntrastatCommon
from odoo.addons.point_of_sale.tests.common import CommonPosTest, TestPoSCommon


@tagged('post_install', '-at_install')
class TestStockIntrastatPOS(TestStockIntrastatCommon, CommonPosTest, TestPoSCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time("2025-10-28 12:54:34")
    def test_report_intrastat_region_with_pos(self):
        """ Test that the Intrastat region is correctly taken from the warehouse linked to the POS order.
        """
        config = self.basic_config
        config.warehouse_id.intrastat_region_id = self.warehouse.intrastat_region_id

        pos_product = self.create_product("POS Test Product", self.categ_basic, 100.0)
        pos_order, _ = self.create_backend_pos_order({
            'pos_config': config,
            'line_data': [{
                'product_id': pos_product.id,
                'price_unit': 100.0,
                'price_subtotal': 100.0,
                'price_subtotal_incl': 0,
            }],
            'order_data': {
                'partner_id': self.partner_a.id,
            },
            'payment_data': [
                {'payment_method_id': self.cash_pm1.id, 'amount': 100.0},
            ],
        })
        pos_order._generate_pos_order_invoice()

        # Generate the Intrastat report
        report = self.env.ref('account_intrastat.intrastat_report')
        options = self._generate_options(report, '2025-10-01', '2025-10-31')
        lines = report._get_lines({**options, 'unfold_all': True})

        self.assertEqual(len(lines), 5)    # 2 report lines (header & total) + 3 lines per POS invoice (header, invoice, & total)

        # Check that the Intrastat region code is taken from the warehouse
        intrastat_region_line = lines[2]
        self.assertEqual(intrastat_region_line.columns[3].no_format, '2000')    # Assuming the 4th column is the Intrastat region column
