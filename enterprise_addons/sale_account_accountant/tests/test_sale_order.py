from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestSaleOrder(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_bank_statement_line_sale_order(self):
        statement_line = self.env['account.bank.statement.line'].create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'date': '2019-01-01',
            'payment_ref': 'line_1',
            'amount': 100.0,
        })
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner.id,
            'order_line': [
                Command.create({
                    'product_id': self.product_a.id,
                    'price_unit': 1000.0,
                })
            ]
        })
        sale_order.action_confirm()

        downpayment = self.env['sale.advance.payment.inv'].with_context({
            'active_ids': [sale_order.id],
            'default_journal_id': self.company_data['default_journal_sale'].id,
            'bank_rec_widget_statement_line_id': statement_line.id,
        }).sudo().create({
            'advance_payment_method': 'fixed',
            'fixed_amount': 100.0,
        })
        downpayment.create_invoices()
        self.assertTrue(statement_line.is_reconciled)

    def test_combo_excluded_from_invoiced_not_delivered(self):
        """A combo product line is not listed in the Invoiced Not Delivered report."""
        product_a, product_b = self.env['product.product'].create([
            {'name': "Burger", 'type': 'consu', 'invoice_policy': 'order'},
            {'name': "Fries", 'type': 'consu', 'invoice_policy': 'order'},
        ])
        combo_a, combo_b = self.env['product.combo'].create([
            {'name': "Main", 'combo_item_ids': [Command.create({'product_id': product_a.id})]},
            {'name': "Side", 'combo_item_ids': [Command.create({'product_id': product_b.id})]},
        ])
        product_combo = self.env['product.product'].create({
            'name': "Meal Menu",
            'type': 'combo',
            'combo_ids': [Command.link(combo_a.id), Command.link(combo_b.id)],
        })
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': product_combo.id,
                'product_uom_qty': 1,
                'price_unit': 0,
            })],
        })
        sale_order.order_line = [Command.create({
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 5.0,
            'combo_item_id': combo.combo_item_ids.id,
            'linked_line_id': sale_order.order_line.id,
        }) for product, combo in zip(product_a + product_b, combo_a + combo_b)]
        sale_order.action_confirm()
        sale_order._create_invoices()
        sale_order.invoice_ids.action_post()

        combo_parent = sale_order.order_line.filtered(lambda l: l.product_id.type == 'combo')
        deferred_ids = self.env['sale.order.line']._get_accrual_line_ids('deferred').ids
        self.assertNotIn(
            combo_parent.id, deferred_ids,
            "Combo parent line must be excluded from the Invoiced Not Delivered report.",
        )

    @freeze_time('2020-01-15')
    def test_read_group_accrual_sale_order_line(self):
        """Test the aggregation of non-stored accrual fields for SO lines."""

        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner.id,
            'date_order': '2020-01-01 12:00:00',
            'order_line': [
                Command.create({
                    'product_id': self.product_a.id,
                    'product_uom_qty': 10.0,
                    'price_unit': 100.0,
                })
            ]
        })
        sale_order.action_confirm()
        sale_order.order_line.qty_delivered = 4.0
        domain = [('order_id', '=', sale_order.id)]
        aggregates = [
            'qty_delivered_at_date:sum',
            'qty_invoiced_at_date:sum',
            'amount_to_invoice_at_date:sum'
        ]
        ctx = {'accrual_entry_date': '2020-01-15'}
        result1, result2 = [
            self.env['sale.order.line']
            .with_context(ctx)
            ._read_group(domain=domain, groupby=[groupby], aggregates=aggregates)
            for groupby in ['order_partner_id', 'create_date:year']
        ]
        _partner_group, sum_delivered, sum_invoiced, sum_amount = result1[0]

        self.assertEqual(sum_delivered, 4.0)
        self.assertEqual(sum_invoiced, 0.0)
        self.assertEqual(sum_amount, 400.0)
        self.assertEqual(result1[0][1:], result2[0][1:])

    def test_delivery_line_excluded_from_invoiced_not_delivered(self):
        """A delivery line is not listed in the Invoiced Not Delivered report."""
        if not "is_delivery" in self.env["sale.order.line"]:
            self.skipTest("Delivery module is not installed.")
        sale_order = (
            self.env['sale.order'].with_context(tracking_disable=True).sudo().create({
                'partner_id': self.partner.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product_a.id,
                        'product_uom_qty': 1,
                        'price_unit': 0,
                    })
                ],
            })
        )
        delivery_product = self.env['product.product'].create({
            'name': 'Delivery',
            'type': 'service',
            'invoice_policy': 'order',
        })
        delivery_line = (
            self.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': delivery_product.id,
                'is_delivery': True,
            })
        )
        sale_order.action_confirm()
        sale_order._create_invoices()
        sale_order.invoice_ids.action_post()

        deferred_ids = self.env['sale.order.line']._get_accrual_line_ids('deferred').ids
        self.assertNotIn(
            delivery_line.id,
            deferred_ids,
            "Delivery line must be excluded from the Invoiced Not Delivered report.",
        )
