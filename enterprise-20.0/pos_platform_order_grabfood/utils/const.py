# Part of Odoo. See LICENSE file for full copyright and licensing details.
MENU_STATUS_MAPPING = {
    'QUEUEING': 'queuing',
    'PROCESSING': 'processing',
    'SUCCESS': 'done',
    'FAILED': 'failed',
}

SERVICE_TYPE_MAPPING = {
    'DeliveredByGrab': 'delivery',
    'TakeAway': 'pickup',
    'DeliveredByRestaurant': 'delivery',
    'DineIn': 'dine_in',
}

ORDER_ACCEPTANCE_TYPE_START_STATUS = {
    'MANUAL': 'new',
    'AUTO': 'accepted',
}

ORDER_STATUS_MAPPING = {
    'DRIVER_ALLOCATED': 'driver_allocated',
    'DRIVER_ARRIVED': 'driver_arrived',
    'COLLECTED': 'collected',
    'DELIVERED': 'delivered',
    'CANCELLED': 'cancelled',
    'FAILED': 'failed',
}

MENU_PRICE_TAX_INCLUSIVE_COUNTRIES = ['SG', 'TH', 'PH', 'VN']

COUNTRIES_CURRENCY_EXPONENT = {
    'SG': 2,
    'MY': 2,
    'ID': 2,
    'VN': 0,
    'TH': 2,
    'PH': 2,
    'KH': 2,
    'MM': 2,
}
