# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged
from odoo.addons.stock_barcode.tests.test_barcode_client_action import TestBarcodeClientAction


@tagged('post_install', '-at_install')
class TestPickingBarcodeClientAction(TestBarcodeClientAction):
    def test_create_product_from_barcode_lookup(self):
        mocked_barcodelookup_response = {
            "products": {
                "barcode_number": "510002952387",
                "product_name": "Some product",
            }
        }

        target_method = "odoo.addons.product_barcodelookup.tools.barcode_lookup_service.barcode_lookup_request"

        self.picking_type_in.restrict_scan_product = 'mandatory'
        self.assertFalse(self.env['product.product'].search([('barcode', '=', '510002952387')], limit=1))
        with patch(target_method, return_value=mocked_barcodelookup_response):
            self.start_tour('/odoo/barcode', 'test_create_product_from_barcode_lookup', login='admin')
        self.assertTrue(self.env['product.product'].search([('barcode', '=', '510002952387')], limit=1))

    def test_no_create_product_from_barcode_lookup(self):
        self.env['res.users'].create({
            'name': 'Barcode User No Product Create',
            'login': 'barcode_user_no_product_create',
            'group_ids': [Command.set([
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        self.picking_type_in.restrict_scan_product = 'mandatory'
        self.assertFalse(self.env['product.product'].search([('barcode', '=', '510002952387')], limit=1))
        self.start_tour('/odoo/barcode', 'test_no_create_product_from_barcode_lookup', login='barcode_user_no_product_create')
