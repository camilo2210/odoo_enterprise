from .common import TestInterCompanyRulesCommonSOPO
from odoo import Command
from odoo.tests import Form, tagged


@tagged('-at_install', 'post_install')
class TestInterCompanyOthers(TestInterCompanyRulesCommonSOPO):

    _test_user_groups = None  # FIXME list needed groups

    def test_00_auto_purchase_on_normal_sales_order(self):
        partner1 = self.env['res.partner'].create({'name': 'customer', 'email': 'from.customer@example.com'})
        my_service = self.env['product.product'].create({
            'name': 'my service',
            'type': 'service',
            'service_tracking': 'subcontract',
            'seller_ids': [(0, 0, {
                'partner_id': self.company_a.partner_id.id,
                'min_qty': 1,
                'price': 10,
                'product_code': 'C01',
                'product_name': 'Name01',
                'sequence': 1,
            })]
        })
        so = self.env['sale.order'].create({
            'partner_id': partner1.id,
            'order_line': [
                (0, 0, {
                    'name': my_service.name,
                    'product_id': my_service.id,
                    'product_uom_qty': 1,
                })
            ],
        })
        # confirming the action from the test will use Odoobot which results in the same flow as
        # confirming the SO from an email link
        so.action_confirm()

        po = self.env['purchase.order'].search([('partner_id', '=', self.company_a.partner_id.id)], order='id desc', limit=1)
        self.assertEqual(po.order_line.label, "[C01] Name01")

    def test_bill_to_po_matching(self):
        # Activate intercompany transactions between company A & company B for both SO and Bills.
        (self.company_a | self.company_b).update({
            'intercompany_generate_sales_orders': True,
            'intercompany_generate_bills_refund': True,
        })

        # Create a PO in company A with vendor as company B.
        po_lines_values = [
            {
                'name': 'service',
                'product_id': self.product_consultant,
                'product_qty': 1,
                'price_unit': 450.0,
                'discount': 10.0,
            },
            {
                'name': 'product a',
                'product_id': self.product_a,
                'product_qty': 3,
                'price_unit': 159.0,
                'discount': 0.0,
            },
            {
                'name': 'product b',
                'product_id': self.product_b,
                'product_qty': 2,
                'price_unit': 259.0,
                'discount': 20.0,
            },
        ]
        purchase_order = Form(self.env['purchase.order'])
        purchase_order.company_id = self.company_a
        purchase_order.partner_id = self.company_b.partner_id
        purchase_order = purchase_order.save()

        with Form(purchase_order) as po:
            for po_line_values in po_lines_values:
                with po.order_line.new() as line:
                    line.name = po_line_values.get('name')
                    line.product_id = po_line_values.get('product_id')
                    line.product_qty = po_line_values.get('product_qty')
                    line.price_unit = po_line_values.get('price_unit')
                    line.discount = po_line_values.get('discount')

        purchase_order.button_confirm()

        # The SO is created in company B. Validate it.
        sale_order = self.env['sale.order'].search([('auto_purchase_order_id', '=', purchase_order.id)], limit=1)
        sale_order.action_confirm()

        # Create the invoice in company B and post it.
        self.env['sale.advance.payment.inv'].create({
            'advance_payment_method': 'delivered',
            'sale_order_ids': [Command.set(sale_order.ids)],
        }).create_invoices()
        sale_order.invoice_ids.action_post()

        # The bill is created in company A.
        bill = self.env['account.move'].search([('auto_invoice_id', '=', sale_order.invoice_ids.id)], limit=1)

        # The bill lines should be matched with the original PO lines.
        for bill_line, po_line in zip(bill.line_ids, purchase_order.order_line):
            self.assertEqual(bill_line.purchase_line_id, po_line)
