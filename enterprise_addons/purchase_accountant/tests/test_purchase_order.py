from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestPurchaseOrder(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time('2020-01-15')
    def test_read_group_accrual_purchase_order_line(self):
        """Test the aggregation of non-stored accrual fields for PO lines."""

        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'date_order': '2020-01-01 12:00:00',
            'order_line': [
                Command.create({
                    'product_id': self.product_a.id,
                    'product_qty': 10.0,
                    'price_unit': 100.0,
                })
            ]
        })

        purchase_order.button_confirm()
        purchase_order.order_line.qty_received = 4.0
        domain = [('order_id', '=', purchase_order.id)]
        aggregates = [
            'qty_received_at_date:sum',
            'qty_invoiced_at_date:sum',
            'amount_to_invoice_at_date:sum'
        ]
        ctx = {'accrual_entry_date': '2020-01-15'}
        result1, result2 = [
            self.env['purchase.order.line']
            .with_context(ctx)
            ._read_group(domain=domain, groupby=[groupby], aggregates=aggregates)
            for groupby in ['partner_id', 'date_order:year']
        ]
        _partner_group, sum_received, sum_invoiced, sum_amount = result1[0]

        self.assertEqual(sum_received, 4.0)
        self.assertEqual(sum_invoiced, 0.0)
        self.assertEqual(sum_amount, 400.0)
        self.assertEqual(result1[0][1:], result2[0][1:])
