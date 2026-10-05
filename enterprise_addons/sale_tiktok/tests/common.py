from datetime import datetime

from odoo.tests import TransactionCase

ORDER_ID_MOCK = "580193230867958565"

BUYER_ADDRESS_MOCK = {
    "address_detail": "Su***************",
    "address_line1": "Su****************",
    "address_line2": "",
    "address_line3": "",
    "address_line4": "",
    "district_info": [
        {"address_level": "L0", "address_level_name": "Country", "address_name": "Indonesia"},
        {"address_level": "L1", "address_level_name": "province", "address_name": "Jakarta"},
        {"address_level": "L2", "address_level_name": "city", "address_name": "South Jakarta"},
        {"address_level": "L3", "address_level_name": "Sub-district", "address_name": "Se*******"},
        {
            "address_level": "L4",
            "address_level_name": "Urban Community",
            "address_name": "Se********",
        },
    ],
    "first_name": "",
    "first_name_local_script": "",
    "full_address": "Indonesia, Jakarta, South Jakarta, Se*******, Se********,Su*******",
    "last_name": "",
    "last_name_local_script": "",
    "name": "a***",
    "phone_number": "(+86)123******43",
    "postal_code": "",
    "region_code": "ID",
}

PAYMENT_MOCK = {
    "buyer_service_fee": "0",
    "currency": "IDR",
    "original_shipping_fee": "1",
    "original_total_product_price": "10000",
    "platform_discount": "0",
    "seller_discount": "0",
    "shipping_fee": "1",
    "shipping_fee_cofunded_discount": "0",
    "shipping_fee_platform_discount": "0",
    "shipping_fee_seller_discount": "0",
    "sub_total": "10000",
    "tax": "0",
    "total_amount": "10001",
}

ORDER_ITEM_MOCK = {
    "buyer_service_fee": "1000",
    "currency": "IDR",
    "display_status": "AWAITING_COLLECTION",
    "id": "1234",
    "is_gift": False,
    "original_price": "10000",
    "package_id": "1162106018708884261",
    "package_status": "TO_FULFILL",
    "platform_discount": "0",
    "product_id": "1731432205220938862",
    "product_name": "Test Product Test Product 1",
    "rts_time": 1000000000,
    "sale_price": "10000",
    "seller_discount": "0",
    "seller_sku": "1234",
    "shipping_provider_id": "6617675021119438849",
    "shipping_provider_name": "TT Virtual# JNT express",
    "sku_id": "1731432230997951598",
    "sku_image": "https://test",
    "sku_name": "Default",
    "sku_type": "NORMAL",
    "tracking_number": "17398843105328",
}

ORDER_MOCK = {
    "next_page_token": False,
    "orders": [
        {
            "id": ORDER_ID_MOCK,
            "buyer_email": "v4bECUSG764MNA5YINJMPPJTTKO3Q@scs1.tiktok.com",
            "buyer_message": "",
            "cancel_order_sla_time": 1579215600,
            "collection_due_time": 1579042800,
            "collection_time": 1579042800,
            "commerce_platform": "TIKTOK_SHOP",
            "create_time": 1578956400,
            "delivery_option_id": "6956553057215710977",
            "delivery_option_name": "Global Standard Shipping(Test)",
            "delivery_time": 1578956400,
            "delivery_type": "HOME_DELIVERY",
            "fulfillment_type": "FULFILLMENT_BY_SELLER",
            "has_updated_recipient_address": False,
            "is_cod": False,
            "is_on_hold_order": False,
            "is_replacement_order": False,
            "is_sample_order": False,
            "paid_time": 1578956400,
            "payment_method_name": "Credit/debit card",
            "rts_sla_time": 1578956400,
            "rts_time": 1578956400,
            "shipping_due_time": 1579042800,
            "shipping_provider": "TT Virtual# JNT express",
            "shipping_provider_id": "6617675021119438849",
            "shipping_type": "TIKTOK",
            "status": "AWAITING_COLLECTION",
            "tracking_number": "17398843105328",
            "tts_sla_time": 1578956400,
            "update_time": 1578956400,
            "user_id": "7496200873847458597",
            "warehouse_id": "7498560733279340293",
            "line_items": [ORDER_ITEM_MOCK],
            "payment": PAYMENT_MOCK,
            "recipient_address": BUYER_ADDRESS_MOCK,
        }
    ],
}


GET_ACCESS_TOKEN_RESPONSE_MOCK = {
    "access_token": "dummy_access_token",
    "access_token_expire_in": 1000000000,
    "refresh_token": "dummy_access_token",
    "refresh_token_expire_in": 1000000000,
    "open_id": "1234",
    "seller_name": "dummy_shop",
    "seller_base_region": "ID",
    "user_type": 0,
}

GET_AUTHORIZED_SHOP_MOCK = {
    "shops": [
        {
            "id": "1234",
            "name": "dummy_name",
            "region": "ID",
            "cipher": "dummy_cipher",
            "code": "1234",
        }
    ]
}

GET_PACKAGE_MOCK = {"doc_url": "https://tiktokshop.com/dummy_url", "tracking_number": "1234"}

GET_PRODUCT_MOCK = {
    "next_page_token": False,
    "products": [
        {
            "create_time": 1747378410,
            "id": "1731432205220938862",
            "skus": [
                {
                    "id": "1731432230997951598",
                    "inventory": [
                        {"quantity": 98, "warehouse_id": "7498560733279340293"},
                        {"quantity": 1, "warehouse_id": "7516069702856214273"},
                    ],
                    "price": {"currency": "IDR", "tax_exclusive_price": "10000"},
                    "seller_sku": "1234",
                }
            ],
            "status": "ACTIVATE",
            "title": "Test Product Test Product 1",
            "update_time": 1750129945,
        }
    ],
    "total_count": 1,
}

GET_WAREHOUSE_MOCK = {
    "warehouses": [
        {
            "address": {
                "address_line1": "Jl. Jenderal Sudirman No.Kav. 25",
                "city": "South Jakarta City",
                "contact_person": "TikTok Shop Partner Center",
                "distict": "Setiabudi",
                "full_address": "Jl. Jenderal Sudirman No.Kav. 25",
                "phone_number": "(+44)07153419266",
                "postal_code": "12920",
                "region": "Republic of Indonesia",
                "region_code": "ID",
                "state": "Jakarta Province",
                "town": "Karet",
            },
            "effect_status": "ENABLED",
            "id": "7498560733279340293",
            "is_default": True,
            "name": "Sandbox ID Local Sales warehouse",
            "sub_type": "DOMESTIC_WAREHOUSE",
            "type": "SALES_WAREHOUSE",
        }
    ]
}

GET_ACTIVE_SHOPS_MOCK = {"shops": [{"id": "dummy_shop_id"}]}

GET_FEES_MOCK = {
    "order_id": "580193230867958565",
    "order_create_time": 1750129945,
    "currency": "IDR",
    "revenue_amount": "12000",
    "fee_and_tax_amount": "-1000",
    "shipping_cost_amount": "-3000",
    "settlement_amount": "9000",
    "sku_transactions": [{}],
    "total_count": 1,
}


OPERATIONS_RESPONSES_MAP = {
    "refresh_token": GET_ACCESS_TOKEN_RESPONSE_MOCK,
    "get_token": GET_ACCESS_TOKEN_RESPONSE_MOCK,
    "get_authorized_shop": GET_AUTHORIZED_SHOP_MOCK,
    "update_inventory": None,
    "get_products": GET_PRODUCT_MOCK,
    "get_order_list": ORDER_MOCK,
    "get_order_detail": ORDER_MOCK,
    "get_package_label": GET_PACKAGE_MOCK,
}


# Test class for common TikTok Shop-related functionality
class TestTikTokShopCommon(TransactionCase):
    def setUp(self):
        super().setUp()
        self.initial_sync_date = datetime(2020, 1, 1)

        self.shop = self.env["tiktok.shop"].create({
            "name": "dummy_name",
            "tiktok_shop_ref": "dummy_shop_id",
            "tiktok_cipher": "dummy_cipher",
            "app_key": "dummy_app_key",
            "app_secret": "dummy_app_secret",
            "service_extern_id": "dummy_service",
            "last_orders_sync_date": self.initial_sync_date,
            "access_token": "dummy_access_token",
            "access_token_expire_datetime": datetime(2020, 6, 1),
            "refresh_token": "dummy_refresh_token",
            "refresh_token_expire_datetime": datetime(2025, 6, 1),
        })

        # Create a product
        self.product = self.env["product.product"].create({
            "name": "Test Product 1",
            "type": "consu",
            "default_code": ORDER_ITEM_MOCK["seller_sku"],
            "list_price": 0.0,
            "taxes_id": None,
            "is_storable": True,
        })

        # Create a TikTok Shop item linked to the product
        self.item = self.env["tiktok.item"].create({
            "product_id": self.product.id,
            "shop_id": self.shop.id,
            "tiktok_sku_extern_id": ORDER_ITEM_MOCK["sku_id"],
            "tiktok_item_extern_id": ORDER_ITEM_MOCK["product_id"],
            "last_inventory_sync_date": self.initial_sync_date,
        })
