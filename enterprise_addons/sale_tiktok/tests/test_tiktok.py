# Part of Odoo. See LICENSE file for full copyright and licensing details.
# pylint: disable=protected-access
from datetime import datetime
from unittest.mock import patch

from freezegun import freeze_time

from odoo import _, fields
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from odoo.addons.sale_tiktok import utils
from odoo.addons.sale_tiktok.tests import common


@tagged("post_install", "-at_install")
class TestTikTokShop(common.TestTikTokShopCommon):
    # pylint: disable=attribute-defined-outside-init,too-many-public-methods

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.startClassPatcher(freeze_time("2020-02-01"))

    # Order
    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_orders_full(self):
        """Test the orders synchronization with on-the-fly creation of all required records."""
        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=lambda _shop, operation_, *_args, **_kwargs: common.OPERATIONS_RESPONSES_MAP[
                operation_
            ],
        ):
            self.shop._sync_orders(auto_commit=False)
            order = self.env["sale.order"].search([("tiktok_order_ref", "=", common.ORDER_ID_MOCK)])
            order_lines = order.order_line
            product_line = order_lines.filtered(lambda line: line.product_id.default_code == "1234")

            expected_dt = datetime.fromtimestamp(
                common.OPERATIONS_RESPONSES_MAP["get_order_list"]["orders"][0]["update_time"]
            )
            self.assertEqual(self.shop.last_orders_sync_date, expected_dt)
            self.assertEqual(len(order), 1)
            self.assertEqual(len(order_lines), 2)  # product line + shipping
            self.assertRecordValues(
                order,
                [
                    {
                        "origin": _("TikTok Shop Order %(order)s", order=common.ORDER_ID_MOCK),
                        "date_order": datetime(2020, 1, 13, 23),
                        "company_id": self.shop.company_id.id,
                        "user_id": self.shop.user_id.id,
                        "team_id": self.shop.team_id.id,
                        "warehouse_id": self.shop.fbs_warehouse_id.id,
                        "amount_total": 10001.0,
                    }
                ],
            )
            self.assertRecordValues(
                product_line,
                [
                    {
                        "price_unit": 10000.0,
                        "product_uom_qty": 1.0,
                        "product_id": self.item.product_id.id,
                    }
                ],
            )

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_orders_partial(self):
        """Test the orders synchronization interruption with API throttling."""

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            """Return a mocked response or raise a TikTokRateLimitError without making an actual
            call to the TikTok Shop API."""
            response_ = common.OPERATIONS_RESPONSES_MAP[operation_]
            if operation_ == "get_order_list":
                self.list_call_count += 1
                if self.list_call_count == 1:
                    return {
                        "orders": [{**common.ORDER_MOCK["orders"][0]}],
                        "next_page_token": "page_2",
                    }

                if self.list_call_count == 2:
                    raise utils.TikTokRateLimitError(operation_)
            return response_

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            self.list_call_count = 0
            self.shop._sync_orders(auto_commit=False)

            expected_dt = datetime.fromtimestamp(
                common.OPERATIONS_RESPONSES_MAP["get_order_list"]["orders"][0]["update_time"]
            )
            self.assertEqual(
                self.shop.last_orders_sync_date,
                expected_dt,
                msg=(
                    "The last_orders_sync_date should advance to the last successfully "
                    "processed order when throttling occurs."
                ),
            )

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_orders_fail(self):
        """Test the orders synchronization cancellation with API throttling.

        The last order synchronization date should not be updated if the rate limit of one operation
        was reached.
        """

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            """Return a mocked response or raise a TikTokRateLimitError without making an actual
            call to the TikTok Shop API."""
            if operation_ == "get_order_list":
                raise utils.TikTokRateLimitError(operation_)
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            last_orders_sync_date_copy = self.shop.last_orders_sync_date
            self.shop._sync_orders(auto_commit=False)
            self.assertEqual(self.shop.last_orders_sync_date, last_orders_sync_date_copy)

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_orders_no_active_shop(self):
        """Test the orders synchronization cancellation with no active shop.

        No order synchronization should be performed as there is no active shop
        """

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            last_orders_sync_date_copy = self.shop.last_orders_sync_date
            self.shop.write({"active": False})

            self.shop._sync_orders(auto_commit=False)

            self.assertEqual(self.shop.last_orders_sync_date, last_orders_sync_date_copy)

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_orders_not_authorized_shop(self):
        """Ensure order synchronization is skipped for an unauthorized shop."""

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            last_orders_sync_date_copy = self.shop.last_orders_sync_date

            self.shop.write({
                "access_token": False,
                "access_token_expire_datetime": False,
                "refresh_token": False,
                "refresh_token_expire_datetime": False,
            })

            self.shop._sync_orders(auto_commit=False)

            self.assertEqual(self.shop.last_orders_sync_date, last_orders_sync_date_copy)

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_orders_cancel(self):

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            order_status_ = "CANCELLED" if self.order_created else "AWAITING_COLLECTION"
            if operation_ == "get_order_list":
                return {"orders": [{**common.ORDER_MOCK["orders"][0], "status": order_status_}]}
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            # Sync an order created on TikTok Shop.
            order_count = self.env["sale.order"].search_count([])
            self.order_created = False
            self.shop._sync_orders(auto_commit=False)
            self.assertEqual(self.env["sale.order"].search_count([]), order_count + 1)

            # Rewind last_orders_sync_date to simulate the order was created before the current time
            self.shop.last_orders_sync_date = datetime.fromtimestamp(1578956400)

            # Sync an order canceled from TikTok Shop.
            self.order_created = True
            self.shop._sync_orders(auto_commit=False)
            order = self.env["sale.order"].search([("tiktok_order_ref", "=", "580193230867958565")])
            self.assertEqual(order.state, "cancel")

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_orders_cancel_abort(self):

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            response_ = common.OPERATIONS_RESPONSES_MAP[operation_]
            order_status_ = "CANCELLED" if self.order_cancelled else "AWAITING_COLLECTION"
            if operation_ == "get_order_list":
                response_ = {
                    "orders": [{**common.ORDER_MOCK["orders"][0], "status": order_status_}]
                }
            return response_

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            # Sync an order created on TikTok Shop.
            self.order_cancelled = False
            self.shop._sync_orders(auto_commit=False)

            # Rewind last_orders_sync_date to simulate the order was created before the current time
            self.shop.last_orders_sync_date = datetime.fromtimestamp(1579050000)

            # Check the order state and validate the picking.
            order = self.env["sale.order"].search([("tiktok_order_ref", "=", common.ORDER_ID_MOCK)])
            picking = self.env["stock.picking"].search([("sale_id", "=", order.id)])
            self.order_cancelled = True

            self.shop._sync_orders(auto_commit=False)

            self.assertEqual(order.state, "cancel")
            self.assertEqual(picking.state, "cancel")

    #  Inventory
    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_inventory(self):

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **kwargs):
            body = kwargs.get("body")
            if operation_ == "update_inventory":
                self.body = body
                return common.OPERATIONS_RESPONSES_MAP[operation_]
            self.assertTrue(False, msg="Should never reach this point")

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            self.shop.synchronize_inventory = True

            self.assertEqual(self.shop.tiktok_item_ids, self.item)
            self.assertEqual(self.item.product_id.free_qty, 0)
            self.assertEqual(self.item.last_inventory_sync_date, self.initial_sync_date)

            # setup inventory level of the product to 10
            location = self.env.ref("stock.stock_location_stock")
            self.env["stock.quant"]._update_available_quantity(self.item.product_id, location, 10)
            self.shop._sync_inventory(auto_commit=False)

            self.assertEqual(self.body["skus"][0]["id"], self.item.tiktok_sku_extern_id)
            self.assertEqual(self.body["skus"][0]["inventory"][0]["quantity"], 10)
            self.assertEqual(self.item.last_inventory_sync_date, fields.Datetime.now())

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_inventory_is_skipped_when_disabled(self):
        """Test skipping the inventory synchronization when the shop disabled the feature.

        No inventory synchronization should be performed when the shop is disabled.
        """

        def get_tiktok_api_response_mock(
            _shop, operation_, _params=None, _path_params=None, _body=None
        ):
            if operation_ == "update_inventory":
                self.assertTrue(False, msg="Should never reach this point")
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            self.shop.synchronize_inventory = False
            self.assertEqual(self.shop.tiktok_item_ids, self.item)

            # No error means get_tiktok_api_response_mock is not called
            self.shop._sync_inventory(auto_commit=False)

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_inventory_not_authorized_shop(self):
        """Ensure inventory synchronization is skipped for an unauthorized shop."""
        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
        ) as mock_patch:
            self.shop.write({
                "access_token": False,
                "access_token_expire_datetime": False,
                "refresh_token": False,
                "refresh_token_expire_datetime": False,
                "synchronize_inventory": True,
            })
            self.assertEqual(self.shop.tiktok_item_ids, self.item)

            self.shop._sync_inventory(auto_commit=False)
            mock_patch.assert_not_called()

    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_inventory_error(self):
        """Test the inventory synchronization error handling.

        An exception should be raised when the inventory synchronization fails.
        """

        class ApiMockError(utils.TikTokApiError):
            def __init__(self, shop):
                super().__init__(
                    shop=shop,
                    operation="update_inventory",
                    request_id="REQ-1",
                    error_code="ERROR",
                    error_message="Mock failure",
                )

        class HandleSyncFailureMockError(Exception):
            pass

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            if operation_ == "update_inventory":
                raise ApiMockError(_shop)
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        def _handle_sync_failure(_shop, **_kwargs):
            raise HandleSyncFailureMockError

        with (
            patch(
                "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
                new=get_tiktok_api_response_mock,
            ),
            patch(
                "odoo.addons.sale_tiktok.models.tiktok_shop.TikTokShop._handle_sync_failure",
                new=_handle_sync_failure,
            ),
        ):
            self.shop.synchronize_inventory = True
            self.assertEqual(self.shop.tiktok_item_ids, self.item)
            with self.assertRaises(HandleSyncFailureMockError):
                self.shop._sync_inventory(auto_commit=False)

    #  Picking
    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_sync_pickings(self):
        """Test the pickings synchronization.

        A tracking number and shipping label should be created.
        """

        def get_tiktok_api_response_mock(_shop, operation_, *_args, **_kwargs):
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=get_tiktok_api_response_mock,
        ):
            # Synchronize the order and generate picking
            self.shop._sync_orders(auto_commit=False)
            order = self.env["sale.order"].search([("tiktok_order_ref", "=", common.ORDER_ID_MOCK)])
            picking = self.env["stock.picking"].search([("sale_id", "=", order.id)])

            self.assertEqual(len(picking), 1)
            self.assertEqual(order.carrier_id.name, "TT Virtual# JNT express")
            self.assertFalse(picking.tiktok_label_attachment_id)

            # Synchronize the picking
            picking._action_done()
            self.env["stock.picking"]._sync_tiktok_pickings()
            self.assertEqual(picking.carrier_tracking_ref, "1234")

            messages = picking.message_ids.filtered(lambda m: m.subject == "TikTok Shop Label")
            self.assertEqual(len(messages), 1)

    #  Product
    def test_find_matching_product_search(self):
        """Test the product search based on the internal reference.

        A product should be found with the internal reference.
        """
        product = self.shop._find_matching_product(
            common.ORDER_ITEM_MOCK["seller_sku"], None, None, None
        )
        self.assertEqual(product.name, self.item.product_id.name)
        self.assertEqual(product.default_code, common.ORDER_ITEM_MOCK["seller_sku"])

    def test_find_matching_product_use_fallback(self):
        """Test the product search failure with use of the fallback.

        A fallback product should be returned when the product is not found.
        """
        default_product = self.env["product.product"].create({
            "name": "Default Name",
            "type": "consu",
        })
        self.env["ir.model.data"].create({
            "module": "sale_tiktok",
            "name": "test_xmlid",
            "model": "product.product",
            "res_id": default_product.id,
        })

        self.assertTrue(self.shop._find_matching_product("UNKNOWN_CODE", "test_xmlid", None, None))

    def test_find_matching_product_regen_fallback(self):
        """Test the product search failure with regeneration of the fallback.

        A restored fallback product should be returned when the product is not found.
        """
        self.env["ir.model.data"].create({
            "module": "sale_tiktok",
            "name": "test_xmlid",
            "model": "product.product",
        })
        product = self.shop._find_matching_product(
            "INCORRECT_CODE", "test_xmlid", "Default Name", "consu"
        )

        self.assertRecordValues(
            product,
            [
                {
                    "name": "Default Name",
                    "type": "consu",
                    "list_price": 0,
                    "sale_ok": False,
                    "purchase_ok": False,
                }
            ],
        )

    def test_find_matching_product_no_fallback(self):
        """Test the product search failure without regeneration of the fallback.

        No product should be returned when product is not found based on internal reference and
        fallback is disabled.
        """
        self.assertFalse(
            self.shop._find_matching_product(
                "INCORRECT_CODE", "test_xmlid", "Default Name", "consu", fallback=False
            )
        )
        self.assertFalse(self.env.ref("sale_tiktok.test_xmlid", raise_if_not_found=False))

    def test_find_matching_product_get_default_shipping(self):
        """Test the product search and get the default shipping product.

        No new item should be created when the default code is updated when
        an existing TikTok item with the same item_identifier is found
        """
        item_count = self.env["tiktok.item"].search_count([])
        product = self.shop._find_matching_product(
            "non_existing_sku", "shipping_product", "TikTok Shop Shipping", "service"
        )

        self.assertEqual(self.env["tiktok.item"].search_count([]), item_count)
        self.assertEqual(product.name, "TikTok Shop Shipping")
        self.assertEqual(product.type, "service")
        self.assertNotEqual(product.default_code, "non_existing_sku")

    #  Partner
    def test_get_partners_no_creation_same_partners(self):
        """Test the partners search with contact as delivery.

        No contact should be created.
        """
        with patch(
            "odoo.addons.sale_tiktok.utils.make_tiktok_api_request",
            new=lambda _shop, operation_, **_kwargs: common.OPERATIONS_RESPONSES_MAP[operation_],
        ):
            country_id = self.env["res.country"].search([("code", "=", "ID")], limit=1).id
            self.env["res.partner"].create({
                "name": "a***",
                "is_company": False,
                "street": "Su****************",
                "street2": "",
                "zip": "",
                "city": "South Jakarta",
                "country_id": country_id,
                "state_id": self
                .env["res.country.state"]
                .search([("country_id", "=", country_id), ("name", "=", "Jakarta")], limit=1)
                .id,
                "phone": "(+86)123******43",
                "customer_rank": 1,
                "company_id": self.shop.company_id.id,
                "tiktok_buyer_extern_id": "7496200873847458597",
            })
            contacts_count = self.env["res.partner"].search_count([])

            contact, delivery = self.shop._find_or_create_partners_from_data(
                common.ORDER_MOCK["orders"][0]
            )
            self.assertEqual(self.env["res.partner"].search_count([]), contacts_count)
            self.assertRecordValues(
                contact, [{"id": delivery.id, "type": "contact", "phone": "(+86)123******43"}]
            )

    def test_get_partners_creation_delivery(self):
        """Test the partners search with creation of the delivery.

        A delivery partner should be created when a field of the address is not strictly the
        same as that of the contact.
        """
        self.env["res.partner"].create({
            "name": "Gederic Frilson",
            "company_id": self.shop.company_id.id,
            "tiktok_buyer_extern_id": 7496200873847458597,
        })
        partners_count = self.env["res.partner"].search_count([])
        contact, delivery = self.shop._find_or_create_partners_from_data(
            common.ORDER_MOCK["orders"][0]
        )

        self.assertNotEqual(contact.id, delivery.id)
        self.assertEqual(self.env["res.partner"].search_count([]), partners_count + 1)

        self.assertRecordValues(
            delivery,
            [{"type": "delivery", "parent_id": contact.id, "company_id": self.shop.company_id.id}],
        )

    def test_get_partners_creation_contact(self):
        """Test the partners search with creation of the contact.

        A contact partner should be created when the contact is not found.
        """
        partners_count = self.env["res.partner"].search_count([])

        contact, delivery = self.shop._find_or_create_partners_from_data(
            common.ORDER_MOCK["orders"][0]
        )

        self.assertEqual(self.env["res.partner"].search_count([]), partners_count + 1)

        country_id = self.env["res.country"].search([("code", "=", "ID")], limit=1).id
        state_id = (
            self
            .env["res.country.state"]
            .search([("country_id", "=", country_id), ("code", "=", "JK")], limit=1)
            .id
        )
        self.assertRecordValues(
            contact,
            [
                {
                    "id": delivery.id,
                    "name": "a***",
                    "type": "contact",
                    "street": "Su****************",
                    "street2": "",
                    "zip": "",
                    "city": "South Jakarta",
                    "country_id": country_id,
                    "state_id": state_id,
                    "phone": "(+86)123******43",
                    "customer_rank": 1,
                    "company_id": self.shop.company_id.id,
                }
            ],
        )

    #  Item
    def test_find_or_create_item_exist(self):
        """Test the item search of _find_or_create_item().

        An existing item will be found without creating a new one.
        """
        item_count = self.env["tiktok.item"].search_count([])
        item = self.shop._find_or_create_item(
            common.ORDER_ITEM_MOCK["seller_sku"],
            common.ORDER_ITEM_MOCK["product_id"],
            common.ORDER_ITEM_MOCK["sku_id"],
        )

        self.assertEqual(self.env["tiktok.item"].search_count([]), item_count)
        self.assertEqual(item.id, self.item.id)
        self.assertEqual(item.sync_to_tiktok, True)

    def test_find_or_create_item_new_item_product(self):
        """Test the item creation and product restoration of _find_or_create_item().

        A new item will be created and the default product will be linked.
        """
        item_count = self.env["tiktok.item"].search_count([])
        item = self.shop._find_or_create_item(
            "a_new_sku", "any_item_identifier", "any_sku_identifier"
        )

        self.assertEqual(self.env["tiktok.item"].search_count([]), item_count + 1)
        self.assertEqual(item.product_id.name, "TikTok Shop Sale")
        self.assertEqual(item.product_id.default_code, False)
        self.assertEqual(item.tiktok_item_extern_id, "any_item_identifier")
        self.assertEqual(item.tiktok_sku_extern_id, "any_sku_identifier")

    def test_find_or_create_item_new_item(self):
        """Test the item creation with no product restoration of _find_or_create_item().

        A new item will be created and linked to an existing product with the same default code.
        """
        item_count = self.env["tiktok.item"].search_count([])
        item = self.shop._find_or_create_item(
            common.ORDER_ITEM_MOCK["seller_sku"], "any_item_identifier", ""
        )

        self.assertEqual(self.env["tiktok.item"].search_count([]), item_count + 1)

        self.assertEqual(item.product_id.name, self.product.name)
        self.assertEqual(item.product_id.default_code, common.ORDER_ITEM_MOCK["seller_sku"])
        self.assertRecordValues(
            item,
            [
                {
                    "tiktok_item_extern_id": "any_item_identifier",
                    "tiktok_sku_extern_id": "",
                    "sync_to_tiktok": True,
                }
            ],
        )

    def test_find_or_create_item_change_item_product(self):
        """Test TikTok item search and update its linked product of _find_or_create_item().

        An existing item will be found and its linked product will be changed.
        """
        item_count = self.env["tiktok.item"].search_count([])
        default_product = self.env.ref("sale_tiktok.default_sale_product")
        self.item.update({"product_id": default_product})
        item = self.shop._find_or_create_item(
            self.product.default_code,
            common.ORDER_ITEM_MOCK["product_id"],
            common.ORDER_ITEM_MOCK["sku_id"],
        )

        self.assertEqual(
            self.env["tiktok.item"].search_count([]),
            item_count,
            "No new item should be created when the default code is changed with the same"
            " item_identifier.",
        )
        self.assertEqual(item.product_id.name, self.product.name)
        self.assertEqual(item.product_id.default_code, self.product.default_code)
        msg = "The correct product should now be assigned to the item."
        self.assertNotEqual(item.product_id, default_product, msg)
