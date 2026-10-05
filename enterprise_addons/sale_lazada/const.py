# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Lazada integration constants.

Contains API endpoints, operation mappings, status mappings, and API limits
for Lazada integration.
"""

AUTH_URL = "https://auth.lazada.com/oauth/authorize"

# API Paths
API_ENDPOINTS = {
    "VN": "https://api.lazada.vn/rest/",
    "SG": "https://api.lazada.sg/rest/",
    "PH": "https://api.lazada.com.ph/rest/",
    "MY": "https://api.lazada.com.my/rest/",
    "TH": "https://api.lazada.co.th/rest/",
    "ID": "https://api.lazada.co.id/rest/",
    "ALL": "https://auth.lazada.com/rest/",
}

ALLOWED_LAZADA_DOC_HOSTS = {
    "lazada.com",
    "lazada.sg",
    "lazada.vn",
    "lazada.co.th",
    "lazada.co.id",
    "lazada.com.my",
    "lazada.com.ph",
}

# Mapping of Lazada API operations to their respective URL path, HTTP method, and API type
API_OPERATIONS_MAPPING = {
    "GenerateAccessToken": {"url_path": "auth/token/create", "api_type": "public"},
    "RefreshAccessToken": {"url_path": "auth/token/refresh", "api_type": "public"},
    "GetSeller": {"url_path": "seller/get", "api_type": "seller"},
    "GetOrders": {"url_path": "orders/get", "api_type": "order"},
    "GetMultipleOrderItems": {"url_path": "orders/items/get", "api_type": "order"},
    "GetShipmentProvider": {"url_path": "order/shipment/providers/get", "api_type": "fulfillment"},
    "GetProducts": {"url_path": "products/get", "api_type": "product"},
    "UpdateSellableQuantity": {"url_path": "product/stock/sellable/update", "api_type": "product"},
    "PackagePack": {"url_path": "order/fulfill/pack", "api_type": "fulfillment"},
    "PrintAWB": {"url_path": "order/package/document/get", "api_type": "fulfillment"},
    "SetReadyToShip": {"url_path": "order/package/rts", "api_type": "fulfillment"},
}

# Mapping of Lazada fulfillment type to Lazada status to synchronize
ORDER_STATUSES_TO_SYNC = {"fbm": {"pending"}, "fbl": {"confirmed"}}

# Mapping of Lazada order item statuses to Odoo order item statuses
ORDER_ITEM_STATUS_MAPPING = {
    "pending": "draft",
    "packed": "confirmed",
    "ready_to_ship_pending": "processing",
    "ready_to_ship": "processing",
    "shipped": "delivered",
    "delivered": "delivered",
    "confirmed": "delivered",
    "canceled": "canceled",
}

# Supported shipping provider types
SUPPORTED_SHIPPING_PROVIDER_TYPES = {"express", "standard", "economy"}

# Mapping of country codes to timezone names for Lazada-supported countries
COUNTRY_TIMEZONE_MAPPING = {
    "VN": "Asia/Ho_Chi_Minh",
    "SG": "Asia/Singapore",
    "PH": "Asia/Manila",
    "MY": "Asia/Kuala_Lumpur",
    "TH": "Asia/Bangkok",
    "ID": "Asia/Jakarta",
}

# Lazada API's limits
ORDER_LIST_DAYS_LIMIT = 15
ORDER_LIST_SIZE_LIMIT = 100
ORDER_DETAIL_SIZE_LIMIT = 50
PRODUCT_LIST_SIZE_LIMIT = 50
SET_RTS_SIZE_LIMIT = 20
SYNC_INVENTORY_SIZE_LIMIT = 50
MAX_API_RETRIES = 3
