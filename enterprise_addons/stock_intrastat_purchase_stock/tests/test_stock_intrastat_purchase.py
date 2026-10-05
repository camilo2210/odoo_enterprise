from freezegun import freeze_time

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.stock_intrastat.tests.common import TestStockIntrastatCommon


@tagged('post_install', '-at_install')
class TestStockIntrastatPurchase(TestStockIntrastatCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time("2025-10-28 12:54:34")
    def test_report_intrastat_region_with_purchase(self):
        """ Test that the Intrastat region is correctly taken from the warehouse linked to the purchase order.
        """
        picking_type = self.env['stock.picking.type'].create({
            'name': 'new_picking_type',
            'code': 'incoming',
            'sequence_code': 'IN',
            'warehouse_id': self.warehouse.id,
        })
        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_qty': 5.0,
                'price_unit': 100.0,
            })],
            'picking_type_id': picking_type.id,
        })
        purchase_order.button_confirm()
        self.env['stock.picking'].search([('purchase_id', '=', purchase_order.id)]).button_validate()
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'purchase_line_id': purchase_order.order_line.id,
                'product_id': self.product.id,
                'quantity': 5.0,
                'price_unit': 100.0,
            })],
            'purchase_vendor_bill_id': self.env['purchase.bill.union'].browse(-purchase_order.id),
        })
        invoice.action_post()

        # Create a vendor bill without purchase order
        vendor_bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'quantity': 2.0,
                'price_unit': 100.0,
            })],
        })
        vendor_bill.action_post()

        # Generate the Intrastat report
        report = self.env.ref('account_intrastat.intrastat_report')
        options = self._generate_options(report, '2025-10-01', '2025-10-31')
        lines = report._get_lines({**options, 'unfold_all': True})

        self.assertEqual(len(lines), 8)    # 2 report lines (header & total) + 2 x 3 lines per invoice (header, invoice, & total)

        # Check that the Intrastat region code is taken from the warehouse
        intrastat_region_line = lines[4]
        self.assertEqual(intrastat_region_line.columns[3].no_format, '2000')    # Assuming the 4th column is the Intrastat region column

        # Check that the Intrastat region code of vendor bill is taken from the default company region
        intrastat_region_line = lines[2]
        self.assertEqual(intrastat_region_line.columns[3].no_format, '1000')    # Assuming the 4th column is the Intrastat region column
