from freezegun import freeze_time

from odoo.fields import Command
from odoo.tests import tagged
from odoo.addons.stock_intrastat.tests.common import TestStockIntrastatCommon
from odoo.addons.sale_stock.tests.common import TestSaleStockCommon


@tagged('post_install', '-at_install')
class TestStockIntrastatSale(TestStockIntrastatCommon, TestSaleStockCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time("2025-10-28 12:54:34")
    def test_report_intrastat_region_with_sale(self):
        """ Test that the Intrastat region is correctly taken from the warehouse linked to the sale order.
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 5.0,
                'price_unit': 100.0,
            })],
            'warehouse_id': self.warehouse.id,
        })
        sale_order.action_confirm()

        # Create an invoice for the sale order
        invoice = sale_order._create_invoices()
        invoice.action_post()

        # Create an invoice without sale order
        normal_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'quantity': 3.0,
                'price_unit': 100.0,
            })],
        })
        normal_invoice.action_post()

        # Generate the Intrastat report
        report = self.env.ref('account_intrastat.intrastat_report')
        options = self._generate_options(report, '2025-10-01', '2025-10-31')
        lines = report._get_lines({**options, 'unfold_all': True})

        self.assertEqual(len(lines), 8)    # 2 report lines (header & total) + 2 x 3 lines per invoice (header, invoice, & total)

        # Check that the Intrastat region code is taken from the warehouse
        intrastat_region_line = lines[4]
        self.assertEqual(intrastat_region_line.columns[3].no_format, '2000')    # Assuming the 4th column is the Intrastat region column

        # Check that the Intrastat region code of normal invoice is taken from the default company region
        intrastat_region_line = lines[2]
        self.assertEqual(intrastat_region_line.columns[3].no_format, '1000')    # Assuming the 4th column is the Intrastat region column
