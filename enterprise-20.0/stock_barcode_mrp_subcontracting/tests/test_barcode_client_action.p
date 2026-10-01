# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest import skip

from odoo import Command
from odoo.addons.stock_barcode.tests.test_barcode_client_action import TestBarcodeClientAction
from odoo.tests import Form, tagged


@tagged('post_install', '-at_install')
class TestSubcontractingBarcodeClientAction(TestBarcodeClientAction):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.subcontractor_partner = cls.env['res.partner'].create({'name': 'Pastry Cook'})
        cls.subcontracted_product, cls.subcontracted_component = cls.env['product.product'].create([
            {
                'name': 'Chocolate Eclairs',
                'is_storable': True,
                'barcode': 'product_subcontracted',
            }, {
                'name': 'Chocolate',
                'is_storable': True,
            },
        ])
        cls.bom = cls.env['mrp.bom'].create({
            'type': 'subcontract',
            'subcontractor_ids': [Command.link(cls.subcontractor_partner.id)],
            'product_tmpl_id': cls.subcontracted_product.product_tmpl_id.id,
            'bom_line_ids': [Command.create({
                'product_id': cls.subcontracted_component.id,
                'product_qty': 1,
            })]
        })

    def test_receipt_classic_subcontracted_product(self):
        self.env.user.write({'group_ids': [Command.link(self.env.ref('stock.group_stock_multi_locations').id)]})
        receipt_picking = self.env['stock.picking'].create({
            'partner_id': self.subcontractor_partner.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type_in.id,
        })
        self.env['stock.move'].create({
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'product_id': self.subcontracted_product.id,
            'uom_id': self.uom_unit.id,
            'product_uom_qty': 2,
            'picking_id': receipt_picking.id,
        })
        receipt_picking.action_confirm()

        url = self._get_client_action_url(receipt_picking)
        self.start_tour(url, 'test_receipt_classic_subcontracted_product', login='admin', timeout=180)

        self.assertEqual(receipt_picking.state, 'done')
        self.assertEqual(receipt_picking.move_ids.quantity, 2)
        self.assertTrue(receipt_picking.move_line_ids.filtered(lambda ml: ml.location_dest_id == self.shelf1))
        self.assertTrue(receipt_picking.move_line_ids.filtered(lambda ml: ml.location_dest_id == self.shelf2))
        sub_order = self.env['mrp.production'].search([('product_id', '=', self.subcontracted_product.id)])

    @skip('Todo after freeze')
    def test_receipt_tracked_subcontracted_product(self):
        self.subcontracted_component.tracking = 'lot'
        lot_id = self.env['stock.lot'].create({
            'product_id': self.subcontracted_component.id,
            'name': 'C01',
        })
        subcontract_location = self.subcontractor_partner.property_stock_subcontractor
        self.env['stock.quant']._update_available_quantity(self.subcontracted_component, subcontract_location, 5, lot_id=lot_id)

        receipt_picking = self.env['stock.picking'].create({
            'partner_id': self.subcontractor_partner.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type_in.id,
        })
        self.env['stock.move'].create({
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'product_id': self.subcontracted_product.id,
            'uom_id': self.uom_unit.id,
            'product_uom_qty': 5,
            'picking_id': receipt_picking.id,
        })
        receipt_picking.action_confirm()

        url = self._get_client_action_url(receipt_picking)
        self.start_tour(url, 'test_receipt_tracked_subcontracted_product', login='admin', timeout=180)
        self.assertEqual(receipt_picking.state, 'assigned')
        self.assertEqual(receipt_picking.move_ids.quantity, 5)

    def test_receipt_subcontract_bom_product_manual_add_src_location(self):
        """ Having a receipt for some product which has a subcontract bom: if the transfer is
        opened in barcode and the form is used to add another move line (for the same product), the
        src location of the new move line should also be the subcontract location.
        """
        receipt = self.env['stock.picking'].create({
            'name': 'TRSBPMASL picking',
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type_in.id,
            'partner_id': self.subcontractor_partner.id,
            'move_ids': [Command.create({
                'location_id': self.supplier_location.id,
                'location_dest_id': self.stock_location.id,
                'product_id': self.subcontracted_product.id,
                'product_uom_qty': 1,
            })],
        })
        receipt.action_confirm()

        url = self._get_client_action_url(receipt)
        self.start_tour(url, 'test_receipt_subcontract_bom_product_manual_add_src_location', login='admin', timeout=180)

        self.assertEqual(receipt.move_line_ids.location_id, self.env.company.subcontracting_location_id)

    def test_partial_subcontract_receipt_and_backorder(self):
        receipt = self.env['stock.picking'].create({
            'name': "test_partial_subcontract_receipt_and_backorder",
            'picking_type_id': self.stock_location.warehouse_id.in_type_id.id,
            'partner_id': self.subcontractor_partner.id,
        })
        self.env['stock.move'].create([{
            'product_id': prod.id,
            'product_uom_qty': 5,
            'uom_id': self.subcontracted_product.uom_id.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_id': receipt.id,
        } for prod in [self.subcontracted_product, self.subcontracted_component]])
        receipt.action_confirm()

        # Ensure user has a mail setup
        user_login = 'admin'
        user_partner = self.env['res.users'].search([('login', '=', user_login)]).partner_id
        if not user_partner.email:
            user_partner.email = 'admin@yourcompany.example.com'

        url = self._get_client_action_url(receipt)
        self.start_tour(url, 'test_partial_subcontract_receipt_and_backorder', login=user_login)

        self.assertEqual(receipt.state, 'done')
        self.assertTrue(receipt.backorder_ids)

    def test_partial_subcontract_receipt_exit_without_validating(self):
        """
        Scan a part of a subcontracted receipt in Barcode and leave it without validating:
        the remaining quantity must still be shown as to be scanned and the receipt must
        still be linked to a single subcontracting MO, as nothing was received yet.
        """
        receipt = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_in.id,
            'partner_id': self.subcontractor_partner.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'move_ids': [Command.create({
                'product_id': self.subcontracted_product.id,
                'product_uom_qty': 5,
                'location_id': self.supplier_location.id,
                'location_dest_id': self.stock_location.id,
            })],
        })
        receipt.action_confirm()
        move = receipt.move_ids
        self.assertRecordValues(move._get_subcontract_production(), [{'product_qty': 5, 'state': 'confirmed'}])

        # Scan 2 out of 5, then leave Barcode without validating.
        move.move_line_ids.quantity = 2
        move.move_line_ids.picked = True
        move.post_barcode_process({})

        # The scanned quantity and the remaining one to scan are kept apart, and the
        # subcontracting MO is left untouched.
        self.assertRecordValues(move.move_line_ids, [
            {'quantity': 2, 'picked': True},
            {'quantity': 3, 'picked': False},
        ])
        self.assertRecordValues(move._get_subcontract_production(), [{'product_qty': 5, 'state': 'confirmed'}])

        # Validating afterwards (Barcode and the form view both call button_validate)
        # receives the scanned quantity and backorders the rest, each with its own MO.
        action = receipt.button_validate()
        Form.from_action(self.env, action).save().process()
        self.assertEqual(receipt.state, 'done')
        self.assertRecordValues(receipt.move_ids._get_subcontract_production(), [{'product_qty': 2, 'state': 'done'}])
        self.assertEqual(receipt.backorder_ids.move_ids.quantity, 3)
        self.assertRecordValues(
            receipt.backorder_ids.move_ids._get_subcontract_production(),
            [{'product_qty': 3, 'state': 'confirmed'}],
        )
