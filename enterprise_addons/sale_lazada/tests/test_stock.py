# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import Command
from odoo.tests.common import MockHTTPClient, tagged

from odoo.addons.sale_lazada.tests import common
from odoo.addons.stock.tests.common import TestStockCommon


@tagged("post_install", "-at_install")
class TestStock(common.TestLazadaCommon, TestStockCommon):
    def setUp(self):
        super().setUp()
        self.pricelist = self.env["product.pricelist"].create({
            "name": "Lazada Pricelist",
            "currency_id": self.env.company.currency_id.id,
        })
        warehouse = self.shop.fbm_warehouse_id
        self.sale_order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "partner_shipping_id": self.partner.id,
            "pricelist_id": self.pricelist.id,
            "company_id": self.shop.company_id.id,
            "warehouse_id": warehouse.id if warehouse else False,
            "lazada_order_ref": str(common.ORDER_ID_MOCK),
            "lazada_shop_id": self.shop.id,
            "lazada_fulfillment_type": "fbm",
            "state": "sale",
            "locked": True,
            "user_id": self.shop.user_id.id,
            "team_id": self.shop.team_id.id,
            "order_line": [
                Command.create({
                    "name": "Test Lazada Product",
                    "product_id": self.product.id,
                    "product_uom_qty": 2,
                    "price_unit": 100.0,
                    "lazada_order_item_ids": [
                        Command.create({"order_item_extern_id": "90001", "status": "draft"})
                    ],
                })
            ],
        })
        self.order_line = self.sale_order.order_line
        self.picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_in.id,
            "location_id": self.supplier_location.id,
            "location_dest_id": self.customer_location.id,
            "company_id": self.shop.company_id.id,
        })
        move_vals = {
            "product_id": self.product.id,
            "product_uom_qty": 1,
            "uom_id": self.product.uom_id.id,
            "picking_id": self.picking.id,
            "location_id": self.supplier_location.id,
            "location_dest_id": self.customer_location.id,
            "company_id": self.shop.company_id.id,
            "sale_line_id": self.order_line.id,
        }
        self.move_1 = self.env["stock.move"].create(move_vals)
        self.picking.sale_id = self.sale_order.id

        self.order_line.lazada_order_item_ids[0].stock_move_id = self.move_1.id
        self.move_1.initialize_lazada_order_items()

    def test_pack_lazada_package(self):
        """Ensure Lazada pickings waiting for packing trigger shipment provider fetch and pack."""
        self.picking.lazada_shipping_allocate_type = False
        self.picking.package_extern_id = False
        self.move_1.lazada_order_item_ids.write({"status": "draft"})

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=lambda operation, _shop, *_args, **_kwargs: common.OPERATIONS_RESPONSES_MAP[
                operation
            ],
        ):
            self.picking._pack_lazada_package()

        self.assertEqual(self.picking.lazada_package_status, "confirmed")
        self.assertEqual(self.picking.lazada_shipping_allocate_type, "NTFS")

    def test_fetch_lazada_shipping_label(self):
        """Ensure fetching shipping labels attaches documents and schedules RTS update."""
        self.picking.package_extern_id = "PKG-001"
        self.picking.carrier_tracking_ref = "TRACK-001"
        self.move_1.lazada_order_item_ids.write({"status": "confirmed"})

        with (
            patch(
                "odoo.addons.sale_lazada.utils.make_lazada_api_request",
                new=lambda operation, _shop, *_args, **_kwargs: common.OPERATIONS_RESPONSES_MAP[
                    operation
                ],
            ),
            MockHTTPClient(method="GET", return_status=200, return_body=b"PDF"),
        ):
            self.picking._fetch_lazada_shipping_label()

        self.assertTrue(
            self.picking.lazada_label_attachment_ids,
            "Fetching labels should store the Lazada label attachment on the picking.",
        )
        self.assertTrue(
            all(
                status == "processing"
                for status in self.picking.move_ids.lazada_order_item_ids.mapped("status")
            ),
            "Fetching labels should move order items to 'processing' status.",
        )

    def test_set_lazada_rts(self):
        """Ensure Ready to Ship API call updates the Lazada package status."""
        self.picking.package_extern_id = "PKG-002"
        self.move_1.lazada_order_item_ids.write({"status": "confirmed"})

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=lambda operation, _shop, *_args, **_kwargs: common.OPERATIONS_RESPONSES_MAP[
                operation
            ],
        ):
            self.picking._set_lazada_rts(self.sale_order.lazada_shop_id)

        self.assertEqual(
            self.picking.lazada_package_status,
            "processing",
            "Successful RTS API calls should move the package status to 'processing'.",
        )

    def test_get_shipment_provider(self):
        """Ensure the shipment provider fetch stores Lazada allocate type."""
        self.picking.lazada_shipping_allocate_type = False
        self.move_1.lazada_order_item_ids.write({"status": "draft"})

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=lambda operation, _shop, *_args, **_kwargs: common.OPERATIONS_RESPONSES_MAP[
                operation
            ],
        ):
            result = self.picking._get_shipment_provider()

        self.assertTrue(result)
        self.assertEqual(
            self.picking.lazada_shipping_allocate_type,
            "NTFS",
            "Fetching the shipment provider should store the shipping allocate type.",
        )
