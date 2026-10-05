# Part of Odoo. See LICENSE file for full copyright and licensing details.

API_ENDPOINTS = "https://open-api.tiktokglobalshop.com"
AUTH_URL = "https://auth.tiktok-shops.com"
AUTH_SERVICES_URL = "https://services.tiktokshop.com/open/authorize"

ALLOWED_TIKTOK_DOC_HOSTS = {
    "tiktokshop.com",
    "tiktokglobalshop.com",
    "tiktokapis.com",
    "byteoversea.com",
    "tiktokstatic.com",
}

# Mapping of TikTok Shop API operations to their respective URL path, HTTP method, and API type
API_OPERATIONS_MAPPING = {
    "refresh_token": {"url_path": "/api/v2/token/refresh", "api_type": "public"},
    "get_token": {"url_path": "/api/v2/token/get", "api_type": "public"},
    "get_authorized_shop": {"url_path": "/authorization/202309/shops", "api_type": "shop"},
    "update_inventory": {
        "url_path": "/product/202309/products/{tiktok_item_extern_id}/inventory/update",
        "method": "POST",
        "api_type": "shop",
    },
    "get_products": {
        "url_path": "/product/202309/products/search",
        "method": "POST",
        "api_type": "shop",
    },
    "get_order_list": {
        "url_path": "/order/202309/orders/search",
        "method": "POST",
        "api_type": "order",
    },
    "get_order_detail": {"url_path": "/order/202309/orders", "api_type": "order"},
    "get_package_label": {
        "url_path": "/fulfillment/202309/packages/{package_id}/shipping_documents",
        "api_type": "package",
    },
    "ship_package": {
        "url_path": "/fulfillment/202309/packages/{package_id}/ship",
        "method": "POST",
        "api_type": "shipping",
    },
}

# Order status to sync from TikTok Shop API
ORDER_STATUSES_TO_SYNC = {"fbs": {"AWAITING_SHIPMENT", "AWAITING_COLLECTION"}}

# Mapping of fulfillment type names of TikTok Shop API
FULFILLMENT_TYPE_MAPPING = {"FULFILLMENT_BY_SELLER": "fbs"}

# Mapping of delivery names of TikTok Shop API
DELIVERY_STATUS_MAPPING = {
    "UNPAID": "draft",
    "AWAITING_SHIPMENT": "draft",
    "AWAITING_COLLECTION": "confirmed",
    "IN_TRANSIT": "done",
    "DELIVERED": "done",
    "COMPLETED": "done",
    "CANCELLED": "canceled",
}

# TikTok Shop API's limits
ORDER_LIST_SIZE_LIMIT = 100
ORDER_DETAIL_SIZE_LIMIT = 50
SHIPPING_DOCUMENT_SIZE_LIMIT = 50
PRODUCT_LIST_SIZE_LIMIT = 100


TIKTOK_API_ERROR_CODES = {"RATE_LIMIT": 36009002}
