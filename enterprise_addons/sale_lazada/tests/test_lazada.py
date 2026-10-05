# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests.common import freeze_time, tagged
from odoo.tools import mute_logger

from odoo.addons.sale_lazada import const
from odoo.addons.sale_lazada import utils as lazada_utils
from odoo.addons.sale_lazada.tests import common


@tagged("post_install", "-at_install")
@freeze_time("2020-02-01")
class TestLazada(common.TestLazadaCommon):
    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_orders_full(self):
        """
        Test the orders synchronization with on-the-fly creation of all required records.

        An order with a product line is created.
        """
        with (
            patch(
                "odoo.addons.sale_lazada.utils.make_lazada_api_request",
                new=lambda operation, _shop, *_args, **_kwargs: common.OPERATIONS_RESPONSES_MAP[
                    operation
                ],
            ),
            patch(
                "odoo.addons.sale_lazada.models.lazada_shop.LazadaShop._compute_subtotal",
                new=lambda _self, total_, *_args, **_kwargs: total_,
            ),
        ):
            self.shop._sync_orders(auto_commit=False)
            order = self.env["sale.order"].search([("lazada_order_ref", "=", common.ORDER_ID_MOCK)])
            product_line = order.order_line.filtered(
                lambda line: line.product_id.default_code == "TEST-SKU-001"
            )

            self.assertEqual(
                self.shop.last_orders_sync_date,
                fields.Datetime.now(),
                msg="The last_orders_sync_date should be equal to current datetime after a"
                " successful run",
            )
            self.assertEqual(len(order), 1, msg="An order should be created")
            self.assertEqual(
                len(order.order_line),
                2,
                msg="An order should have a product line and a shipping line",
            )
            shipping_line = order.order_line - product_line
            self.assertEqual(len(shipping_line), 1)
            self.assertEqual(shipping_line.price_unit, 10.0)
            self.assertRecordValues(
                order,
                [
                    {
                        "date_order": datetime(2020, 1, 15),
                        "company_id": self.shop.company_id.id,
                        "user_id": self.shop.user_id.id,
                        "team_id": self.shop.team_id.id,
                        "lazada_fulfillment_type": "fbm",
                        "amount_total": 90.0,
                    }
                ],
            )
            self.assertRecordValues(
                product_line,
                [
                    {
                        "price_unit": 80.0,
                        "discount": 0.0,
                        "product_uom_qty": 1.0,
                        "product_id": self.product.id,
                    }
                ],
            )

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_orders_partial(self):
        """
        Test the orders synchronization interruption with API throttling.

        Two orders are available in the response. The first one is fully synchronized, the second
        one is throttled.
        """

        def get_lazada_api_response_mock(operation_, _shop, *_args, **_kwargs):
            """
            Return a mocked response without making an actual call to the Lazada API.
            Raise a LazadaRateLimitError when the second order is synchronized,
            to simulate a throttling issue.
            """
            if operation_ == "GetOrders":
                self.api_call_count += 1
                if self.api_call_count == 2:
                    raise lazada_utils.LazadaRateLimitError(operation_)
                return common.GET_ORDERS_RESPONSE_MOCK
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            self.api_call_count = 0

            self.shop._sync_orders(auto_commit=False)

            orders = self.env["sale.order"].search([
                ("lazada_order_ref", "=", str(common.ORDER_ID_MOCK))
            ])
            self.assertEqual(len(orders), 1, msg="Only one order should be synchronized")
            self.assertEqual(
                self.shop.last_orders_sync_date,
                self.initial_sync_date + timedelta(days=const.ORDER_LIST_DAYS_LIMIT),
                msg="The last_orders_sync_date should be equal to the LastUpdateDate of the last"
                " fully synchronized period.",
            )
            self.assertEqual(self.api_call_count, 2)

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_orders_fail(self):
        """
        Test the orders synchronization cancellation with API throttling.

        The last order synchronization date should not be updated if the rate limit of one operation
        was reached.
        """

        def get_lazada_api_response_mock(operation_, _shop, *_args, **_kwargs):
            """Return a mocked response or raise a LazadaRateLimitError without making an actual
            call to the Lazada API."""
            self.api_call_count += 1
            if operation_ == "GetOrders":
                raise lazada_utils.LazadaRateLimitError(operation_)
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            self.api_call_count = 0
            last_orders_sync_date_copy = self.shop.last_orders_sync_date

            self.shop._sync_orders(auto_commit=False)

            self.assertEqual(self.api_call_count, 1)
            self.assertEqual(self.shop.last_orders_sync_date, last_orders_sync_date_copy)

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_orders_no_active_shop(self):
        """
        Test the orders synchronization cancellation with no active shop.

        No order synchronization should be performed as the shop is inactive.
        """

        def get_lazada_api_response_mock(operation_, _shop, *_args, **_kwargs):
            self.api_call_count += 1
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            self.api_call_count = 0
            last_orders_sync_date_copy = self.shop.last_orders_sync_date
            self.shop.write({"active": False})

            self.env["lazada.shop"]._sync_orders(auto_commit=False)

            self.assertEqual(self.api_call_count, 0)
            self.assertEqual(self.shop.last_orders_sync_date, last_orders_sync_date_copy)

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_orders_fbl(self):
        """Test the orders synchronization with fulfillment type 'Fulfillment By Lazada'.

        An order with a product line is created.
        FBL order should generate a stock move for each product and use the FBL location.
        """

        def get_lazada_api_response_mock(operation_, _shop, *_args, **_kwargs):
            """Return a mocked response with a confirmed order with FBL fulfillment type."""
            if operation_ == "GetOrders":
                return {
                    **common.GET_ORDERS_RESPONSE_MOCK,
                    "data": {"orders": [common.build_order_mock(statuses=["confirmed"])]},
                }
            if operation_ == "GetMultipleOrderItems":
                return {
                    **common.GET_ORDER_ITEMS_RESPONSE_MOCK,
                    "data": [
                        {
                            "order_id": common.ORDER_ID_MOCK,
                            "order_number": common.ORDER_ID_MOCK,
                            "order_items": [
                                {**common.ORDER_ITEM_MOCK, "is_fbl": 1, "status": "confirmed"}
                            ],
                        }
                    ],
                }
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            self.shop._sync_orders(auto_commit=False)
            order = self.env["sale.order"].search([("lazada_order_ref", "=", common.ORDER_ID_MOCK)])

            self.assertEqual(len(order), 1)
            self.assertEqual(order.lazada_fulfillment_type, 'fbl')
            self.assertEqual(
                len(order.order_line),
                2,
                msg="FBL order should have a product line and a shipping line",
            )
            self.assertEqual(
                order.warehouse_id,
                self.shop.fbl_location_id.warehouse_id,
                "FBL orders should use the FBL location's warehouse",
            )

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_orders_cancel(self):
        """
        Test the cancellation synchronization of a Lazada order.

        The order is first imported, then Lazada reports a cancellation that should cancel
        the related sale order and mark the order items as canceled.
        """

        def get_lazada_api_response(operation_, _shop, _params=None, **_kwargs):
            if operation_ == "GetOrders":
                statuses = ["pending"] if not self.order_canceled else ["canceled"]
                return {
                    "code": "0",
                    "request_id": "0_sync_orders_cancel",
                    "data": {
                        "countTotal": 1,
                        "count": 1,
                        "orders": [{**common.build_order_mock(), "statuses": statuses}],
                    },
                }
            if operation_ == "GetMultipleOrderItems":
                status = "pending" if not self.order_canceled else "canceled"
                return {
                    "code": "0",
                    "request_id": "0_sync_orders_cancel_items",
                    "data": [
                        {
                            "order_id": common.ORDER_ID_MOCK,
                            "order_number": common.ORDER_ID_MOCK,
                            "order_items": [{**common.ORDER_ITEM_MOCK, "status": status}],
                        }
                    ],
                }
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with (
            patch(
                "odoo.addons.sale_lazada.utils.make_lazada_api_request", new=get_lazada_api_response
            ),
            patch(
                "odoo.addons.sale_lazada.models.lazada_shop.LazadaShop._compute_subtotal",
                new=lambda _self, total_, *_args, **_kwargs: total_,
            ),
        ):
            self.order_canceled = False

            self.shop._sync_orders(auto_commit=False)

            order = self.env["sale.order"].search([("lazada_order_ref", "=", common.ORDER_ID_MOCK)])
            self.assertEqual(len(order), 1, "Order should be created before cancellation.")
            self.order_canceled = True

            with freeze_time("2020-03-01"):
                self.shop._sync_orders(auto_commit=False)

            self.assertEqual(order.state, "cancel", "Canceled orders should be canceled in Odoo.")
            self.assertTrue(
                all(item.status == "canceled" for item in order.order_line.lazada_order_item_ids),
                "All Lazada order items should be marked as canceled.",
            )

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_inventory(self):
        """
        Test the inventory synchronization to Lazada.

        Verifies that product stock quantities are correctly sent to Lazada API
        when synchronization is enabled.
        """

        def get_lazada_api_response_mock(operation_, _shop, params=None, **_kwargs):
            """Return a mocked response for inventory updates."""
            if operation_ == "UpdateSellableQuantity":
                self.payload = json.loads(params["payload"])
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            self.shop.synchronize_inventory = True
            # Update the stock level of the product
            self.env["stock.quant"]._update_available_quantity(
                self.product, self.shop.fbm_warehouse_id.lot_stock_id, 100
            )

            self.shop._sync_inventory(auto_commit=False)

            item_payload = self.payload["Request"]["Product"]["Skus"]["Sku"][0]
            self.assertEqual(item_payload["SkuId"], str(common.ORDER_ITEM_MOCK["sku_id"]))
            self.assertEqual(item_payload["SellableQuantity"], 100)

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_inventory_is_skipped_when_disabled(self):
        """Test that inventory synchronization is skipped when disabled for the shop."""

        def get_lazada_api_response_mock(operation_, _shop, *_args, **_kwargs):
            """Inventory update should not be called."""
            self.api_call_count += 1
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            self.api_call_count = 0
            self.shop.synchronize_inventory = False
            self.shop._sync_inventory(auto_commit=False)
            self.assertEqual(self.api_call_count, 0)

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_product_catalog_initialization(self):
        """
        Test the product catalog synchronization from Lazada.

        It will be initialized if the shop has no Lazada items.
        """

        def get_lazada_api_response_mock(operation_, _shop, params_=None, *_args, **_kwargs):
            """Return a mocked response for product catalog."""
            params_ = params_ or {}
            if operation_ == "GetProducts":
                self.time_from = params_.get("update_after")
                self.time_to = params_.get("update_before")
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            self.shop.last_product_catalog_sync_date = None
            self.shop.lazada_item_ids = self.env["lazada.item"]
            self.assertEqual(len(self.shop.lazada_item_ids), 0)

            self.shop._sync_product_catalog()

            self.assertEqual(len(self.shop.lazada_item_ids), 1)
            self.assertEqual(
                self.shop.lazada_item_ids.lazada_item_extern_id, common.ORDER_ITEM_MOCK["sku_id"]
            )
            self.assertEqual(self.shop.lazada_item_ids.product_id.default_code, "TEST-SKU-001")
            self.assertTrue(self.shop.lazada_item_ids.sync_lazada_inventory)

            self.assertEqual(self.time_from, None)
            self.assertEqual(self.time_to, None)

            self.assertEqual(self.shop.last_product_catalog_sync_date, datetime(2020, 2, 1))

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_sync_product_catalog_update(self):
        """
        Test the product catalog synchronization from Lazada after the initial synchronization.

        Verifies that new products are added to the catalog and the sync date is updated
        with proper time range parameters sent to the API.
        """

        def get_lazada_api_response_mock(operation_, _shop, params=None, *_args, **_kwargs):
            """Return a mocked response of an updated product for product catalog."""
            params = params or {}
            if operation_ == "GetProducts":
                self.time_from = params.get("update_after")
                self.time_to = params.get("update_before")
                return {
                    **common.GET_PRODUCTS_RESPONSE_MOCK,
                    "data": {
                        "total_products": 1,
                        "products": [
                            {
                                "item_id": 2222222222,
                                "status": "Active",
                                "skus": [
                                    {
                                        "SellerSku": "TEST-SKU-002",
                                        "Status": "active",
                                        "SkuId": 10002,
                                        "fblWarehouseInventories": [],
                                    }
                                ],
                            }
                        ],
                    },
                }
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_lazada.utils.make_lazada_api_request",
            new=get_lazada_api_response_mock,
        ):
            # Create a storable product for the new SKU
            self.env['product.product'].create({
                'name': "Test Product 2",
                'default_code': 'TEST-SKU-002',
                'list_price': 100.0,
                'is_storable': True,
            })
            # Ensure the initial sync date is still the same as before the update
            self.assertEqual(self.shop.last_product_catalog_sync_date, self.initial_sync_date)

            self.shop._sync_product_catalog()

            self.assertEqual(len(self.shop.lazada_item_ids), 2)
            item = self.shop.lazada_item_ids.filtered(lambda i: i.lazada_item_extern_id == "10002")
            self.assertTrue(item)
            self.assertTrue(item.sync_lazada_inventory)

            self.assertEqual(self.time_from, "2020-01-01T07:00:00+07:00")
            self.assertEqual(self.time_to, "2020-02-01T07:00:00+07:00")

            updated_sync_date = lazada_utils.lazada_timestamp_to_datetime(
                "2020-02-01T07:00:00+07:00"
            )
            self.assertEqual(self.shop.last_product_catalog_sync_date, updated_sync_date)

    def test_find_matching_product(self):
        """
        Test the product matching functionality using the internal reference.

        Verifies that existing products are found by SKU and that non-existent products
        return False when fallback is disabled.
        """
        # Test match with existing internal reference
        found_product = self.shop._find_matching_product(
            "TEST-SKU-001", "default_shipping", "Default Shipping", "service"
        )
        self.assertEqual(found_product.id, self.product.id)

        # Test no match with non-existing internal reference
        found_product = self.shop._find_matching_product(
            "NONEXISTENT-SKU", "default_shipping", "Default Shipping", "service", fallback=False
        )
        self.assertFalse(found_product)

    def test_find_or_create_item(self):
        """
        Test the functionality to find or create a Lazada item.

        If the item already exists, it should be found and returned.
        If the item does not exist, it should be created and returned.
        """
        # Test existing item
        found_item = self.shop._find_or_create_item(
            "TEST-SKU-001", common.ORDER_ITEM_MOCK["sku_id"], "fbm"
        )
        self.assertEqual(found_item.id, self.item.id)
        self.assertTrue(
            found_item.sync_lazada_inventory,
            "Existing FBM item with storable product should be marked for synchronization.",
        )

        # Test new item creation
        new_item = self.shop._find_or_create_item("NEW-SKU-001", 98765, "fbm")
        self.assertNotEqual(new_item.id, self.item.id)
        self.assertFalse(
            new_item.sync_lazada_inventory,
            "Non-storable products should not be marked for synchronization.",
        )

    def test_find_or_create_partners_from_data(self):
        """
        Test the creation of partners from order data.

        Verifies that shipping and invoice partners are created with correct address
        details, country, phone, and Lazada buyer external ID from order data.
        """
        with patch(
            "odoo.addons.sale_lazada.models.lazada_shop.LazadaShop._find_matching_product",
            new=lambda _self, _sku, _default_xmlid, _default_name, _default_type, _fallback=True: (
                self.product
            ),
        ):
            order_data = common.build_order_mock()
            order_data['order_items'] = [common.ORDER_ITEM_MOCK]
            partner_shipping, partner_invoice = self.shop._find_or_create_partners_from_data(
                order_data
            )

            self.assertTrue(partner_shipping)
            self.assertTrue(partner_invoice)
            self.assertEqual(partner_shipping.name, "Gederic Frilson")
            self.assertEqual(partner_shipping.country_id.code, "VN")
            self.assertEqual(partner_shipping.lazada_buyer_extern_id, "30001")
            self.assertEqual(partner_shipping.street, "123 RainBowMan Street")
            self.assertEqual(partner_shipping.street2, "Apartment 4B")
            self.assertEqual(partner_shipping.zip, "12345")
            self.assertEqual(partner_shipping.city, "New Duck City")
            self.assertEqual(partner_shipping.phone, "+1 234-567-8910")

    def test_compute_lazada_order_status(self):
        """Test the computation of Lazada delivery status based on order item statuses."""
        order_data = common.build_order_mock()
        order_data['order_items'] = [dict(common.ORDER_ITEM_MOCK)]
        order = self.shop._create_order_from_data(order_data)

        product_line = order.order_line.filtered("lazada_order_item_ids")
        product_line.lazada_order_item_ids.status = "processing"

        self.assertEqual(order.lazada_order_status, "processing")

        # Add another item with a different status to test the mixed statuses
        self.env["lazada.order.item"].create({
            "order_item_extern_id": 456,
            "sale_order_line_id": product_line.id,
            "stock_move_id": product_line.move_ids[0].id,
            "status": "delivered",
        })

        self.assertEqual(order.lazada_order_status, "manual")

    def test_get_lazada_aggregated_status_single_status(self):
        """Should return the status itself when only one status is present."""
        status = lazada_utils.get_lazada_aggregated_status(["processing"])
        self.assertEqual(status, "processing")

    def test_get_lazada_aggregated_status_mixed_statuses(self):
        """Should return 'manual' when statuses are mixed."""
        status = lazada_utils.get_lazada_aggregated_status(["processing", "delivered"])
        self.assertEqual(status, "manual")

    def test_get_lazada_aggregated_status_all_canceled(self):
        """Should return 'canceled' if all statuses are canceled."""
        status = lazada_utils.get_lazada_aggregated_status(["canceled"])
        self.assertEqual(status, "canceled")

    def test_should_create_fbm_order_with_pending_status(self):
        """FBM should create order when status is 'pending'."""
        order_data_fbm_pending = {
            "order_items": [{**common.ORDER_ITEM_MOCK, "shipping_provider_type": "standard"}],
            "statuses": ["pending"],
        }
        self.assertTrue(
            self.shop._should_create_order(order_data_fbm_pending, "fbm"),
            "FBM orders with 'pending' status should be synchronized.",
        )

    def test_should_not_create_fbm_order_with_confirmed_status(self):
        """FBM should not create order when status is 'confirmed'."""
        order_data_fbm_confirmed = {
            "order_id": common.ORDER_ID_MOCK,
            "order_items": [{**common.ORDER_ITEM_MOCK, "shipping_provider_type": "standard"}],
            "statuses": ["confirmed"],
        }
        self.assertFalse(
            self.shop._should_create_order(order_data_fbm_confirmed, "fbm"),
            "FBM orders without 'pending' status should be ignored.",
        )

    def test_should_create_fbl_order_with_confirmed_status(self):
        """FBL should create order when status is 'confirmed'."""
        order_data_fbl_confirmed = {
            "order_items": [
                {**common.ORDER_ITEM_MOCK, "shipping_provider_type": "standard", "is_fbl": 1}
            ],
            "statuses": ["confirmed"],
        }
        self.assertTrue(
            self.shop._should_create_order(order_data_fbl_confirmed, "fbl"),
            "FBL orders with 'confirmed' status should be synchronized.",
        )

    def test_should_not_create_fbl_order_with_pending_status(self):
        """FBL should not create order when status is 'pending'."""
        order_data_fbl_pending = {
            "order_id": common.ORDER_ID_MOCK,
            "order_items": [
                {**common.ORDER_ITEM_MOCK, "shipping_provider_type": "standard", "is_fbl": 1}
            ],
            "statuses": ["pending"],
        }
        self.assertFalse(
            self.shop._should_create_order(order_data_fbl_pending, "fbl"),
            "FBL orders without 'confirmed' status should be ignored.",
        )

    def test_get_fulfillment_type_fbm(self):
        """Ensure that a single FBM order item returns 'fbm' as fulfillment type."""
        fbm_order_data = {
            "order_id": "TESTFBM",
            "order_items": [{**common.ORDER_ITEM_MOCK, "is_fbl": 0}],
        }
        self.assertEqual(self.shop._get_fulfillment_type(fbm_order_data), "fbm")

    def test_get_fulfillment_type_fbl(self):
        """Ensure that a single FBL order item returns 'fbl' as fulfillment type."""
        fbl_order_data = {
            "order_id": "TESTFBL",
            "order_items": [{**common.ORDER_ITEM_MOCK, "is_fbl": 1}],
        }
        self.assertEqual(self.shop._get_fulfillment_type(fbl_order_data), "fbl")

    def test_get_fulfillment_type_mixed(self):
        """Ensure that mixed FBL and FBM order items return None (unsupported)."""
        mixed_order_data = {
            "order_id": "TESTMIX",
            "order_items": [
                {**common.ORDER_ITEM_MOCK, "is_fbl": 0},
                {**common.ORDER_ITEM_MOCK, "is_fbl": 1},
            ],
        }
        self.assertIsNone(self.shop._get_fulfillment_type(mixed_order_data))

    # --- Computed Subtotals --- #

    def test_compute_subtotal_price_include_tax(self):
        """Price-included taxes keep the line subtotal aligned with Shopee's total."""
        currency = self.quick_ref("base.USD")
        subtotal = self.shop._compute_subtotal(10.0, self.tax_price_include_7, currency)

        # subtotal is not rounded to compute the correct unit price
        # but the rounded subtotal should be equal to the total for price-included taxes
        self.assertEqual(subtotal, 10.0)

    def test_compute_subtotal_price_exclude_tax(self):
        """Price-excluded taxes are backed out from Shopee's tax-included total."""
        currency = self.quick_ref("base.USD")
        subtotal = self.shop._compute_subtotal(10.00, self.tax_price_exclude_7, currency)

        # subtotal is not rounded to compute the correct unit price
        # but the rounded subtotal should be equal to the total for price-excluded taxes
        self.assertEqual(subtotal, 9.35)

    # --- Test Adjustment Lines --- #

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_no_adjustment_line_for_tax_exclusive_unit_rounding(self):
        """Tax-exclusive non-divisible unit prices do not emit a rounding adjustment line."""
        self.product.taxes_id = self.tax_price_exclude_7
        # Keep the unrounded tax-exclusive subtotal on the line so Odoo can reconcile exactly.
        items = [
            {
                **common.ORDER_ITEM_MOCK,
                "order_item_id": 90101,
                "item_price": 15.0,
                "paid_price": 10.0,
                "currency": "USD",
            },
            {
                **common.ORDER_ITEM_MOCK,
                "order_item_id": 90102,
                "item_price": 15.0,
                "paid_price": 10.0,
                "currency": "USD",
            },
            {
                **common.ORDER_ITEM_MOCK,
                "order_item_id": 90103,
                "item_price": 15.0,
                "paid_price": 10.0,
                "currency": "USD",
            },
        ]
        order_data = common.build_order_mock(
            order_id="ADJ_RESIDUE_001", items=items, shipping_fee=0, currency="USD"
        )

        order = self.shop._create_order_from_data(order_data)

        adjustment_product = self.env.ref("sale_lazada.default_adjustment_product")
        adjustment_lines = order.order_line.filtered(
            lambda line: line.product_id == adjustment_product
        )
        self.assertEqual(len(adjustment_lines), 0)
        self.assertEqual(order.amount_total, float(order_data["price"]))

    # --- Test Shipping Lines --- #

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_free_shipping_omits_shipping_line(self):
        """``shipping_fee == 0`` produces no shipping line."""
        order_data = common.build_order_mock(
            order_id="FREE_SHIP_001",
            items=[dict(common.ORDER_ITEM_MOCK, order_item_id=90301, paid_price=40.0)],
            shipping_fee=0,
        )

        order = self.shop._create_order_from_data(order_data)

        # Only one line for the one item — no shipping line.
        self.assertEqual(len(order.order_line), 1)

    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_shipping_line_with_tax(self):
        """Shipping line carries product's fiscal-position-mapped tax and reconciles."""
        # Give the default shipping product a 7% price-exclude tax.
        shipping_product = self.env.ref("sale_lazada.default_shipping_product")
        shipping_product.taxes_id = self.tax_price_exclude_7
        self.product.taxes_id = self.tax_price_exclude_7

        # Use shipping fee=10.70 tax-incl; reverse: 10.00 tax-excl. Clean reconciliation.
        items = [
            {
                **common.ORDER_ITEM_MOCK,
                "order_item_id": 90401,
                "item_price": 20.00,
                "paid_price": 20.00,
                "currency": "USD",
            }
        ]
        order_data = common.build_order_mock(
            order_id="SHIP_TAX_001", items=items, shipping_fee=10.70, currency="USD"
        )

        order = self.shop._create_order_from_data(order_data)

        shipping_line = order.order_line.filtered(
            lambda line: line.product_id.id == shipping_product.id
        )
        self.assertEqual(len(shipping_line), 1)
        self.assertEqual(shipping_line.product_uom_qty, 1)
        self.assertEqual(shipping_line.price_unit, 10.00)
        self.assertIn(self.tax_price_exclude_7.id, shipping_line.tax_ids.ids)
        self.assertEqual(order.amount_total, float(order_data["price"]) + 10.70)

    # --- Test _prepare_order_lines_values --- #

    def test_prepare_order_lines_values(self):
        """Product line uses the paid price as unit price; shipping comes from the order."""
        self.product.taxes_id = self.tax_price_include_7
        order_data = common.build_order_mock(shipping_fee=10, currency="USD")

        order = self.shop._create_order_from_data(order_data)

        shipping_product = self.quick_ref("sale_lazada.default_shipping_product")
        product_line = order.order_line.filtered(lambda line: line.product_id == self.product)
        shipping_line = order.order_line.filtered(lambda line: line.product_id == shipping_product)
        self.assertEqual(len(order.order_line), 2)
        self.assertEqual(product_line.product_uom_qty, 1)  # one ORDER_ITEM_MOCK
        self.assertEqual(product_line.price_unit, 80.0)  # paid price
        self.assertEqual(product_line.tax_ids, self.tax_price_include_7)
        self.assertEqual(shipping_line.price_unit, 10.0)

    def test_prepare_order_lines_values_discount_untaxed(self):
        """The order-level voucher becomes one untaxed negative line for a tax-free order."""
        self.product.taxes_id = [Command.clear()]
        order_data = common.build_order_mock(shipping_fee=0, currency="USD", voucher="16.0")

        order = self.shop._create_order_from_data(order_data)

        discount_product = self.quick_ref("sale_lazada.default_discount_product")
        discount_line = order.order_line.filtered(lambda line: line.product_id == discount_product)
        # No product tax → a single untaxed discount line of the order-level voucher.
        # Field access on `discount_line` raises if more than one line matched.
        self.assertEqual(discount_line.price_unit, -16.0)
        self.assertFalse(discount_line.tax_ids)

    def test_prepare_order_lines_values_discount_distributed_per_tax_group(self):
        """The order-level discount is split per tax group, pro-rata to each group's base.

        Bases 200 (7% tax) and 100 (10% tax) share a 9.99 voucher: the larger group is allocated
        first (6.66) and the last group absorbs the exact remainder (3.33), summing to -9.99.
        """
        tax_include_10 = self.env["account.tax"].create({
            "name": "Lazada Test Tax 10% Included",
            "amount": 10.0,
            "price_include_override": "tax_included",
            "tax_group_id": self.tax_price_include_7.tax_group_id.id,
            "country_id": self.quick_ref("base.vn").id,
        })
        self.product.taxes_id = self.tax_price_include_7
        product_2 = self.env["product.product"].create({
            "name": "Second product",
            "default_code": "SKU2",
            "taxes_id": tax_include_10.ids,
        })
        self.env["lazada.item"].create({
            "product_id": product_2.id,
            "shop_id": self.shop.id,
            "lazada_item_extern_id": "20002",
            "lazada_sku": "SKU2",
        })

        items = [
            {
                **common.ORDER_ITEM_MOCK,
                "order_item_id": 90601,
                "paid_price": 200.0,
                "currency": "USD",
            },
            {
                **common.ORDER_ITEM_MOCK,
                "order_item_id": 90602,
                "sku": "SKU2",
                "sku_id": "20002",
                "paid_price": 100.0,
                "currency": "USD",
            },
        ]
        order_data = common.build_order_mock(
            order_id="LZ_DIST_001", items=items, shipping_fee=0, currency="USD", voucher="9.99"
        )

        order = self.shop._create_order_from_data(order_data)

        discount_product = self.quick_ref("sale_lazada.default_discount_product")
        discount_lines = order.order_line.filtered(lambda line: line.product_id == discount_product)
        self.assertEqual(len(discount_lines), 2)  # one negative line per tax group
        # Field access on each filtered line raises if more than one line carries that group's tax.
        line_7 = discount_lines.filtered(lambda line: line.tax_ids == self.tax_price_include_7)
        line_10 = discount_lines.filtered(lambda line: line.tax_ids == tax_include_10)
        self.assertEqual(line_7.price_unit, -6.66)
        self.assertEqual(line_10.price_unit, -3.33)
