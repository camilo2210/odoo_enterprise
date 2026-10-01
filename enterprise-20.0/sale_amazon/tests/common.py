# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase

ORDER_BUYER_INFO_MOCK = {
    "buyerEmail": "iliketurtles@marketplace.amazon.com",
    "buyerName": "Gederic Frilson",
}

ORDER_ADDRESS_MOCK = {
    "addressLine1": "123 RainBowMan Street",
    "phone": "+1 234-567-8910 ext. 12345",
    "postalCode": "12345-1234",
    "city": "New Duck City DC",
    "stateOrRegion": "CA",
    "countryCode": "US",
    "name": "Gederic Frilson",
    "addressType": "COMMERCIAL",
}

ORDER_ITEM_MOCK = {
    "orderItemId": "987654321",
    "quantityOrdered": 2,
    "product": {
        "sellerSku": "TEST",
        "title": "Run Test, Run!",
        "condition": {
            "conditionType": "Used",
            "conditionSubtype": "Acceptable",
            "conditionNote": "DO NOT BUY THIS",
        },
    },
    "fulfillment": {
        "packing": {"giftOption": {"giftMessage": "Wrapped Hello", "giftWrapLevel": "WRAP-CODE"}}
    },
    "proceeds": {
        "breakdowns": [
            {"type": "ITEM", "subtotal": {"amount": "100.00", "currencyCode": "USD"}},
            {"type": "SHIPPING", "subtotal": {"amount": "12.50", "currencyCode": "USD"}},
            {"type": "GIFT_WRAP", "subtotal": {"amount": "3.33", "currencyCode": "USD"}},
            {
                "type": "DISCOUNT",
                "subtotal": {"amount": "7.50", "currencyCode": "USD"},
                "detailedBreakdowns": [
                    {"subtype": "ITEM", "value": {"amount": "5.00", "currencyCode": "USD"}},
                    {"subtype": "SHIPPING", "value": {"amount": "2.50", "currencyCode": "USD"}},
                ],
            },
            {
                "type": "TAX",
                "subtotal": {"amount": "23.83", "currencyCode": "USD"},
                "detailedBreakdowns": [
                    {"subtype": "ITEM", "value": {"amount": "20.00", "currencyCode": "USD"}},
                    {"subtype": "SHIPPING", "value": {"amount": "2.50", "currencyCode": "USD"}},
                    {"subtype": "DISCOUNT", "value": {"amount": "1.50", "currencyCode": "USD"}},
                    {"subtype": "GIFT_WRAP", "value": {"amount": "1.33", "currencyCode": "USD"}},
                ],
            },
        ]
    },
}

FBM_LISTINGS_ITEM_MOCK = {
    "sku": "TESTING_SKU",
    "productTypes": [{"productType": "PRODUCT"}],
    "fulfillmentAvailability": [{"fulfillmentChannelCode": "DEFAULT"}],
}

FBA_LISTINGS_ITEM_MOCK = {
    "sku": "TESTING_SKU",
    "productTypes": [{"productType": "PRODUCT"}],
    "fulfillmentAvailability": [{"fulfillmentChannelCode": "AMAZON_NA"}],
}

SEARCH_LISTINGS_ITEMS_MOCK = {"items": [FBM_LISTINGS_ITEM_MOCK]}

GET_ORDER_MOCK = {
    "buyer": ORDER_BUYER_INFO_MOCK,
    "orderId": "123456789",
    "createdTime": "1378-04-08T00:00:00Z",
    "lastUpdatedTime": "2017-01-20T00:00:00Z",
    "fulfillment": {
        "fulfillmentStatus": "UNSHIPPED",
        "fulfilledBy": "MERCHANT",
        "fulfillmentServiceLevel": "SHIPPING-CODE",
    },
    "proceeds": {"grandTotal": {"currencyCode": "USD", "amount": "120.00"}},
    "salesChannel": {"marketplaceId": "ATVPDKIKX0DER"},
    "recipient": {"deliveryAddress": ORDER_ADDRESS_MOCK},
    "orderItems": [ORDER_ITEM_MOCK],
}

SEARCH_ORDERS_RESPONSE_MOCK = {
    "lastUpdatedBefore": "2020-01-01T00:00:00Z",
    "orders": [GET_ORDER_MOCK],
}

OPERATIONS_RESPONSES_MAP = {
    "getOrder": {"order": GET_ORDER_MOCK},
    "searchOrders": SEARCH_ORDERS_RESPONSE_MOCK,
    "createFeedDocument": {"feedDocumentId": "123123", "url": "my_amazing_feed_url.test"},
    "createFeed": None,
    "searchListingsItems": SEARCH_LISTINGS_ITEMS_MOCK,
}


class TestAmazonCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref("sales_team.group_sale_manager")
        cls.marketplace = cls.env["amazon.marketplace"].search([
            ("api_ref", "=", GET_ORDER_MOCK["salesChannel"]["marketplaceId"])
        ])
        cls.account = cls.env["amazon.account"].create({
            "name": "TestAccountName",
            "seller_key": "Random Seller Key",
            "refresh_token": "A refresh token",
            "base_marketplace_id": cls.marketplace.id,
            "available_marketplace_ids": [cls.marketplace.id],
            "active_marketplace_ids": [cls.marketplace.id],
            "company_id": cls.env.company.id,
        })

        # Create an offer linked to the product
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.product = cls.env["product.product"].create({
            "name": "This is a storable product",
            "is_storable": True,
        })
        cls.offer = cls.env["amazon.offer"].create({
            "account_id": cls.account.id,
            "marketplace_id": cls.marketplace.id,
            "product_id": cls.product.id,
            "sku": "TESTING_SKU",
            "amazon_channel": "fbm",
            "amazon_feed_ref": '{"productType":"PRODUCT"}',
        })

        # Create a delivery method
        cls.carrier = cls.env["delivery.carrier"].create(
            {"name": "My Truck", "product_id": cls.product.id}  # delivery_type == 'fixed'
        )
        cls.tracking_ref = "dummy tracking ref"
