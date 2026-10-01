# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo.addons.base.tests.common import BaseCommon

ORDER_SN_MOCK = "O123456789"

BUYER_ID_MOCK = 2**32  # int64

BUYER_ADDRESS_MOCK = {
    "name": "Gederic Frilson",
    "phone": "9876543210",
    "full_address": "123 RainBowMan Street, Xã Phong Thạnh Tây B, New Duck City DC, Tây Ninh",
    "city": "New Duck City DC",
    "district": "Xã Phong Thạnh Tây B",
    "state": "Tây Ninh",
    "town": "",
    "region": "VN",
    "zipcode": "",
}

ORDER_ITEM_MOCK = {
    "add_on_deal": False,
    "add_on_deal_id": 0,
    "item_id": 111111,
    "item_name": "test product",
    "item_sku": "",
    "model_discounted_price": 40,
    "model_id": 222222,
    "model_original_price": 100,
    "model_quantity_purchased": 4,
    "model_sku": "TEST_SKU",
    "order_item_id": 111111,
    "promotion_group_id": 0,
    "promotion_id": 333333,
    "promotion_type": "flash_sale",
}


def build_order_mock(
    order_sn=ORDER_SN_MOCK, items=None, buyer_paid_shipping_fee=10, currency="VND", **extra
):
    """Build a Shopee order-detail payload for tests.

    The buyer-paid shipping fee is conveyed through the escrow detail (see
    :func:`build_escrow_mock`), not the order detail; it is only used here to compute the
    ``total_amount`` the order must reconcile to. Any keyword in ``extra`` overrides the default
    payload key of the same name, or adds a new key if absent.

    :param str order_sn: Shopee order reference.
    :param list items: List of dicts compatible with ORDER_ITEM_MOCK shape.
    :param float buyer_paid_shipping_fee: Buyer-paid shipping fee included in ``total_amount``.
    :param str currency: Currency code.
    :return: An order-detail payload dict.
    """
    if items is None:
        items = [ORDER_ITEM_MOCK]
    total_amount = (
        sum(item["model_quantity_purchased"] * item["model_discounted_price"] for item in items)
        + buyer_paid_shipping_fee
    )
    payload = {
        "actual_shipping_fee_confirmed": True,
        "buyer_user_id": BUYER_ID_MOCK,
        "buyer_username": "Gederic Frilson",
        "update_time": 1579050000,  # 2020-01-15
        "create_time": 1579050000,  # 2020-01-15
        "currency": currency,
        "fulfillment_flag": "fulfilled_by_local_seller",
        "item_list": items,
        "order_sn": order_sn,
        "order_status": "READY_TO_SHIP",
        "package_list": [
            {
                "item_list": [
                    {
                        "item_id": item["item_id"],
                        "model_id": item["model_id"],
                        "model_quantity": item["model_quantity_purchased"],
                        "order_item_id": item.get("order_item_id", item["item_id"]),
                        "promotion_group_id": 0,
                    }
                    for item in items
                ],
                "package_number": "PKG_" + order_sn,
                "shipping_carrier": "Fake Ship",
            }
        ],
        "recipient_address": BUYER_ADDRESS_MOCK,
        "region": "VN",
        "shipping_carrier": "Fake Ship",
        "total_amount": total_amount,
    }
    payload.update(extra)
    return payload


# Mock data for the response of the getOrders API
GET_ACCESS_TOKEN_RESPONSE_MOCK = {
    "error": "",
    "message": "",
    "request_id": "123456",
    "response": {},
    "refresh_token": "dummy_refresh_token",
    "access_token": "dummy_oauth_token",
    "expire_in": 1000000,
}

REFRESH_TOKEN_RESPONSE_MOCK = {**GET_ACCESS_TOKEN_RESPONSE_MOCK, "partner_id": 100}

GET_ORDER_DETAILS_RESPONSE_MOCK = {"order_list": [build_order_mock()]}


def build_escrow_mock(
    buyer_paid_shipping_fee=10, voucher_from_seller=0, voucher_from_shopee=0, coins=0, **extra
):
    """Build a Shopee escrow-detail payload for tests.

    Carries the buyer-side income breakdown: the buyer-paid shipping fee (the source of the
    shipping line) and the order-level discounts. The defaults mirror :func:`build_order_mock`
    (shipping 10, no discount) so an order reconciles to its ``total_amount`` without an adjustment
    line. Any keyword in ``extra`` overrides or adds an ``order_income`` key.

    :param float buyer_paid_shipping_fee: Buyer-paid shipping fee.
    :param float voucher_from_seller: Seller-funded order-level voucher.
    :param float voucher_from_shopee: Platform-funded order-level voucher.
    :param float coins: Shopee coins redeemed.
    :return: An escrow-detail payload dict.
    """
    return {
        "order_income": {
            "buyer_paid_shipping_fee": buyer_paid_shipping_fee,
            "voucher_from_seller": voucher_from_seller,
            "voucher_from_shopee": voucher_from_shopee,
            "coins": coins,
            **extra,
        }
    }


GET_ESCROW_DETAIL_RESPONSE_MOCK = build_escrow_mock()

GET_ORDER_LIST_RESPONSE_MOCK = {
    "order_list": [{"order_sn": ORDER_SN_MOCK}],
    "more": False,
    "next_cursor": None,
}

GET_SHIPMENT_RESPONSE_MOCK = {
    "result_list": [
        {"status": "READY", "order_sn": ORDER_SN_MOCK, "package_number": "2537708677189632625"}
    ]
}

GET_SHOP_INFO_RESPONSE_MOCK = {
    "shop_name": "mock_shopee_shop",
    "region": "VN",
    "status": "NORMAL",
    "expire_time": 1682179199,
}

# Map of API operations to their corresponding response data
OPERATIONS_RESPONSES_MAP = {
    "refresh_token": REFRESH_TOKEN_RESPONSE_MOCK,
    "get_token": GET_ACCESS_TOKEN_RESPONSE_MOCK,
    "get_shop_info": GET_SHOP_INFO_RESPONSE_MOCK,
    "get_order_list": GET_ORDER_LIST_RESPONSE_MOCK,
    "get_order_detail": {"order_list": [build_order_mock()]},
    "get_escrow_detail": GET_ESCROW_DETAIL_RESPONSE_MOCK,
    "get_tracking_number": {"tracking_number": "MY200448706479IT"},
    "create_shipping_document": {"result_list": [{"order_sn": ORDER_SN_MOCK}]},
    "get_shipping_document_result": GET_SHIPMENT_RESPONSE_MOCK,
    "download_shipping_document": b"%PDF-1.4\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
    "update_stock": None,
}


# Test class for common Shopee-related functionality
class TestShopeeCommon(BaseCommon):
    # See sale.tests.test_sale_order: fixtures need product/tax/stock/ACL rights.
    _test_user_groups = (
        'sales_team.group_sale_manager',
        'product.group_product_manager',
        'account.group_account_manager',
        'stock.group_stock_user',
        'base.group_erp_manager',
    )
    _test_user_name = 'Test Shopee Manager'

    def setUp(self):
        super().setUp()
        # Create a Shopee account
        self.initial_sync_date = datetime(2020, 1, 1)
        self.account = self.env["shopee.account"].create({
            "name": "mock_shopee_account",
            "api_endpoint": "test",
            "partner_identifier": 1,
            "partner_key": "A partner token",
            "company_ids": [self.env.company.id],
        })

        # Create a shop
        self.shop = self.env["shopee.shop"].create({
            "name": GET_SHOP_INFO_RESPONSE_MOCK["shop_name"],
            "shop_identifier": 1,
            "account_id": self.account.id,
            "status": "active",
            "authorization_expiration_date": datetime.now() + timedelta(days=365),
            "last_orders_sync_date": self.initial_sync_date,
        })

        # Create a product
        self.product = self.env["product.product"].create({
            "name": "This is a storable product",
            "type": "consu",
            "default_code": ORDER_ITEM_MOCK["model_sku"],
            "list_price": 0.0,
            "is_storable": True,
        })

        # Create a Shopee item linked to the product
        self.item = self.env["shopee.item"].create({
            "product_id": self.product.id,
            "shop_id": self.shop.id,
            "shopee_item_identifier": ORDER_ITEM_MOCK["item_id"],
            "shopee_model_identifier": ORDER_ITEM_MOCK["model_id"],
            "last_inventory_sync_date": self.initial_sync_date,
            "sync_to_shopee": True,
        })

        country = self.quick_ref("base.vn")
        tax_group = self.env["account.tax.group"].create({
            "name": "Shopee Test Tax Group",
            "country_id": country.id,
        })

        self.tax_price_include_7 = self.env["account.tax"].create({
            "name": "Shopee Test Tax 7% Included",
            "amount": 7.0,
            "price_include_override": "tax_included",
            "tax_group_id": tax_group.id,
            "country_id": country.id,
        })
        self.tax_price_exclude_7 = self.env["account.tax"].create({
            "name": "Shopee Test Tax 7% Excluded",
            "amount": 7.0,
            "price_include_override": "tax_excluded",
            "tax_group_id": tax_group.id,
            "country_id": country.id,
        })
