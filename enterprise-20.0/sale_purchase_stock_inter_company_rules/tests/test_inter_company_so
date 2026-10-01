# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import Form, tagged
from .common import TestInterCompanyRulesCommonStock


@tagged('post_install', '-at_install')
class TestInterCompanySaleToPurchaseWithStock(TestInterCompanyRulesCommonStock):

    _test_user_groups = None  # FIXME list needed groups

    def test_01_inter_company_confirm_purchase_after_delivery(self):
        """ Checks that if inter-company Purchase Orders are generated in a draft state, they can still
            reserve on Inter-Company transit location as if it was an internal location, so that serial delivered
            before the PO validation can still be fetched.
        """
        self.env.user.group_ids |= self.env.ref('stock.group_production_lot')
        self.company_b.write({
            'intercompany_generate_purchase_orders': True,
            'intercompany_sync_delivery_receipt': True,
            'intercompany_document_state': 'draft',
        })
        product = self.env['product.product'].create({
            'is_storable': True,
            'tracking': 'serial',
            'name': 'Cross Serial',
            'company_id': False,
        })
        serial = self.env['stock.lot'].create({'name': 'serial', 'product_id': product.id})
        warehouse_a = self.env['stock.warehouse'].search([('company_id', '=', self.company_a.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(product, warehouse_a.lot_stock_id, quantity=1, lot_id=serial)

        # Create a sale order from Company A to Company B
        with Form(self.env['sale.order'].with_company(self.company_a)) as sale_form:
            sale_form.partner_id = self.company_b.partner_id
            with sale_form.order_line.new() as line:
                line.product_id = product
                line.product_uom_qty = 1
            sale_to_b = sale_form.save()
        sale_to_b.with_company(self.company_a).action_confirm()
        self.assertEqual(len(sale_to_b.picking_ids), 1)

        # Verify that PO is created in company B in draft.
        purchase_from_a = self.env['purchase.order'].with_company(self.company_b).search([('partner_ref', '=', sale_to_b.name)])
        self.assertEqual(purchase_from_a.state, 'draft')

        # Do the delivery of Company A
        interco_location = self.env.ref('stock.stock_location_inter_company')
        delivery = sale_to_b.picking_ids
        self.assertEqual(delivery.location_dest_id, interco_location)
        with Form(delivery) as delivery_form:
            with delivery_form.move_ids.edit(0) as move_form:
                move_form.lot_ids = serial
                move_form.picked = True
            delivery = delivery_form.save()
        delivery.with_company(self.company_a).button_validate()

        # Confirm the PO and check that reservation could be done
        purchase_from_a.with_company(self.company_b).button_confirm()
        self.assertRecordValues(purchase_from_a.picking_ids.move_ids, [{
            'state': 'assigned',
            'quantity': 1,
            'lot_ids': serial.ids,
            'location_id': interco_location.id,
        }])

    def test_02_inter_company_multiple_lines_with_same_product(self):
        """Checks receipt assignment for two inter-company lines with the same product.
        Ensures each incoming move gets its own reserved qty (1 and 1), not a merged 2 and 0 split.
        Prevents regression where reservation was assigned only to the first move.
        """
        self.company_b.write({
            'intercompany_generate_purchase_orders': True,
            'intercompany_sync_delivery_receipt': True,
            'intercompany_document_state': 'posted',
        })
        product = self.env['product.product'].create({
            'is_storable': True,
            'name': 'Product',
            'company_id': False,
        })
        warehouse_a = self.env['stock.warehouse'].search([('company_id', '=', self.company_a.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(product, warehouse_a.lot_stock_id, quantity=2)

        # Create a sale order from Company A to Company B
        sale_to_b = self.env["sale.order"].create({
            "partner_id": self.company_b.partner_id.id,
            "order_line": [
                Command.create({"product_id": product.id, "product_uom_qty": 1}),
                Command.create({"product_id": product.id, "product_uom_qty": 1}),
            ]
        })

        sale_to_b.with_company(self.company_a).action_confirm()
        purchase_from_a = self.env['purchase.order'].with_company(self.company_b).search([('partner_ref', '=', sale_to_b.name)])

        self.assertEqual(len(sale_to_b.picking_ids), 1)
        self.assertEqual(len(sale_to_b.order_line), 2)
        self.assertEqual(len(sale_to_b.picking_ids.move_ids), 2)

        self.assertEqual(len(purchase_from_a.picking_ids), 1)
        self.assertEqual(len(purchase_from_a.order_line), 2)
        self.assertEqual(len(purchase_from_a.picking_ids.move_ids), 2)

        # Do the delivery of Company A
        for move in sale_to_b.picking_ids.move_ids:
            move.quantity = 1
            move.picked = True
        sale_to_b.picking_ids.with_company(self.company_a).button_validate()

        # Ensure the quantity have been reserved correctly in the receipt:
        self.assertRecordValues(purchase_from_a.picking_ids.move_ids, [
            {"product_uom_qty": 1, "quantity": 1},
            {"product_uom_qty": 1, "quantity": 1},
        ])

    def test_03_inter_company_multiple_lines_match_on_price(self):
        self.company_b.write({
            'intercompany_generate_purchase_orders': True,
            'intercompany_sync_delivery_receipt': True,
            'intercompany_document_state': 'posted',
        })
        product = self.env['product.product'].create({
            'is_storable': True,
            'name': 'Product Different Price',
            'company_id': False,
        })
        warehouse_a = self.env['stock.warehouse'].search([('company_id', '=', self.company_a.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(product, warehouse_a.lot_stock_id, quantity=2)

        sale_to_b = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.company_b.partner_id.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1, 'price_unit': 1}),
                Command.create({'product_id': product.id, 'product_uom_qty': 1, 'price_unit': 2}),
            ],
        })
        sale_to_b.with_company(self.company_a).action_confirm()
        purchase_from_a = self.env['purchase.order'].with_company(self.company_b).search([('partner_ref', '=', sale_to_b.name)])

        # Validate delivery last move only
        delivery = sale_to_b.picking_ids
        delivery.move_ids.picked = False
        target_move = delivery.move_ids[-1]
        target_move.quantity = target_move.product_uom_qty
        target_move.picked = True
        delivery.with_context(skip_backorder=True).button_validate()

        # Ensure the quantity have been reserved correctly in the receipt:
        self.assertRecordValues(purchase_from_a.picking_ids.move_ids, [
            {"product_uom_qty": 1, "quantity": 0, "price_unit": 1},
            {"product_uom_qty": 1, "quantity": 1, "price_unit": 2},
        ])

        # Now we try to validate the first move, but with the price in the PO updated
        purchase_from_a.order_line[0].write({"price_unit": 3})

        # Validate delivery last move only
        delivery = sale_to_b.picking_ids[1]
        self.assertTrue(delivery.state != "done")
        # delivery.move_ids.picked = False
        move = delivery.move_ids
        self.assertEqual(len(move), 1)
        move.quantity = move.product_uom_qty
        move.picked = True
        delivery.with_context(skip_backorder=True).button_validate()

        self.assertRecordValues(purchase_from_a.picking_ids.move_ids, [
            {"product_uom_qty": 1, "quantity": 1, "price_unit": 3},
            {"product_uom_qty": 1, "quantity": 1, "price_unit": 2},
        ])
