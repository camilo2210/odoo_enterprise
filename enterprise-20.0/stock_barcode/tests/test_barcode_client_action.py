# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestBarcodeClientAction(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disables the sound effect so we don't go crazy while running the test tours locally.
        cls.env['ir.config_parameter'].set_bool('stock_barcode.mute_sound_notifications', True)

        # User config.
        cls.admin_user = cls.env.ref('base.user_admin')
        cls.env = cls.env(user=cls.admin_user)
        cls.env.user.email = 'mitchell.admin@example.com'
        # Create a company and a warehouse dedicated to the tests and configure its locations.
        cls.company = cls.env['res.company'].create({'name': "Test Company"})
        cls.admin_user.company_ids |= cls.company
        cls.admin_user.company_id = cls.company
        # Warehouse's configuration.
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)])
        cls.warehouse.update({'name': 'Test Warehouse', 'code': 'WH'})
        cls.warehouse.wh_input_stock_loc_id.barcode = 'WHINPUT'
        cls.warehouse.wh_qc_stock_loc_id.barcode = 'WHQUALITY'
        cls.warehouse.wh_output_stock_loc_id.barcode = 'WHOUTPUT'
        cls.warehouse.wh_pack_stock_loc_id.barcode = 'WHPACKING'

        # Create shortcut properties.
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.picking_type_in = cls.warehouse.in_type_id
        cls.picking_type_in.auto_show_allocation_report = False
        cls.picking_type_internal = cls.warehouse.int_type_id
        cls.picking_type_out = cls.warehouse.out_type_id
        cls.picking_type_out.restrict_scan_source_location = 'mandatory'
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_dozen = cls.env.ref('uom.product_uom_dozen')

        # Locations creation.
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.stock_location.barcode = 'LOC-01-00-00'
        cls.shelf3, cls.shelf1, cls.shelf2, cls.shelf4 = cls.env['stock.location'].with_company(cls.company).create([{
            'name': name,
            'location_id': cls.stock_location.id,
            'barcode': barcode,
        } for (name, barcode) in [
            ('Section 3', 'shelf3'),
            ('Section 1', 'LOC-01-01-00'),
            ('Section 2', 'LOC-01-02-00'),
            ('Section 4', 'shelf4'),
        ]])

        # Create some products.
        cls.product1, cls.product2, cls.productserial1, cls.productlot1, cls.product_tln_gtn8, cls.consu1, cls.consu2 = cls.env['product.product'].create([
            {
                'name': 'product1',
                'default_code': 'TEST',
                'is_storable': True,
                'barcode': 'product1',
            }, {
                'name': 'product2',
                'is_storable': True,
                'barcode': 'product2',
            }, {
                'name': 'productserial1',
                'is_storable': True,
                'barcode': 'productserial1',
                'tracking': 'serial',
            }, {
                'name': 'productlot1',
                'is_storable': True,
                'barcode': 'productlot1',
                'tracking': 'lot',
            }, {
                'name': 'Battle Droid',
                'default_code': 'B1',
                'is_storable': True,
                'tracking': 'lot',
                'barcode': '76543210',  # (01)00000076543210 (GTIN-8 format)
            }, {
                'name': 'consu1',
                'is_storable': False,
                'barcode': 'consu1',
            }, {
                'name': 'consu2',
                'is_storable': False,
                'barcode': 'consu2',
            },
        ])
        # Create other records.
        cls.package = cls.env['stock.package'].create({
            'name': 'P00001',
        })
        cls.owner = cls.env['res.partner'].create({
            'name': 'Azure Interior',
        })

    def setUp(self):
        super().setUp()
        # Remove all access rights linked to stock application to "reset" Inventory settings.
        group_uom_id = self.ref('uom.group_uom')
        self.env.ref('base.group_user').write({'implied_ids': [
            Command.unlink(group_uom_id),
            Command.unlink(self.ref('stock.group_stock_multi_locations')),
            Command.unlink(self.ref('stock.group_stock_multi_warehouses')),
            Command.unlink(self.ref('stock.group_stock_picking_batch')),
            Command.unlink(self.ref('stock.group_production_lot')),
            Command.unlink(self.ref('stock.group_tracking_lot')),
        ]})
        self.env.user.write({'group_ids': [Command.unlink(group_uom_id)]})
        self.call_count = 0

    def tearDown(self):
        self.call_count = 0
        super(TestBarcodeClientAction, self).tearDown()

    def _get_client_action_url(self, record):
        return f'/odoo/{record.id}/action-stock_barcode.stock_barcode_picking_client_action'

    def _reset_package_sequence(self, next_number=1):
        """ Resets package sequence to be sure we'll have the attended packages name."""
        seq = self.env['ir.sequence'].search([('code', '=', 'stock.package')])
        seq.number_next_actual = next_number
