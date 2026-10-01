# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestBarcodeLightUser(TransactionCase):
    """ `stock_barcode.group_barcode_user` must be self-sufficient.

    A light user only gets the Barcode privilege (no Inventory app), so every
    right the Barcode app needs must be carried by that group alone.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.barcode_user = cls.env['res.users'].create({
            'name': "Barcode Only",
            'login': "barcode_only",
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('stock_barcode.group_barcode_user').id,
                cls.env.ref('stock.group_production_lot').id,
                cls.env.ref('stock.group_tracking_lot').id,
                cls.env.ref('stock.group_stock_multi_locations').id,
            ])],
        })
        cls.product = cls.env['product.product'].create({
            'name': "Barcoded Product",
            'is_storable': True,
            'barcode': "product_barcode",
        })
        cls.picking_type_internal = cls.env.ref('stock.picking_type_internal')
        cls.stock_location = cls.env.ref('stock.stock_location_stock')

    def test_light_user_is_light(self):
        self.assertEqual(self.barcode_user.role, 'light_user', "the Barcode privilege must not make a user regular")

    def test_barcode_picking_flow(self):
        """ Create, fill, pack and validate a transfer as a barcode-only user. """
        picking = self.env['stock.picking'].with_user(self.barcode_user).create({
            'picking_type_id': self.picking_type_internal.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
        })
        picking.move_ids = [Command.create({
            'product_id': self.product.id,
            'product_uom_qty': 2,
            'location_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
        })]
        self.env['stock.quant']._update_available_quantity(self.product, self.stock_location, 10)
        picking.action_confirm()
        picking.action_assign()
        # The Barcode app loads everything it displays through this method.
        data = picking._get_stock_barcode_data()
        self.assertTrue(data['records']['stock.picking'])
        picking.move_line_ids.write({'quantity': 2, 'picked': True})
        # Packing goes through `stock.package`, `stock.package.type` and `stock.package.history`.
        picking.action_put_in_pack(package_name="PACK-LIGHT")
        self.assertTrue(picking.move_line_ids.result_package_id, "packages must be usable from Barcode")
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def test_barcode_inventory_flow(self):
        """ Count and apply an inventory adjustment as a barcode-only user. """
        quant = self.env['stock.quant'].with_user(self.barcode_user).create({
            'product_id': self.product.id,
            'location_id': self.stock_location.id,
            'inventory_quantity': 5,
        })
        self.assertTrue(quant._get_stock_barcode_data()['records']['stock.quant'])
        quant.action_apply_inventory()
        self.assertEqual(quant.quantity, 5)

    def test_barcode_lot_creation(self):
        """ Lots are created on the fly when scanning them in the Barcode app. """
        self.product.tracking = 'lot'
        lot = self.env['stock.lot'].with_user(self.barcode_user).create({
            'name': "LOT-0001",
            'product_id': self.product.id,
        })
        self.assertTrue(lot.name)

    def test_barcode_main_menu_data(self):
        """ The Barcode main menu counts the operations of each operation type. """
        picking_types = self.env['stock.picking.type'].with_user(self.barcode_user).search([])
        self.assertTrue(picking_types.read(['count_picking_ready']))
