# Part of Odoo. See LICENSE file for full copyright and licensing details.
SERVICE_TYPE_MAPPING = {
    'gofood': 'delivery',
    'gofood_pickup': 'pickup',
}
ORDER_STATUS_MAPPING = {
    'AWAITING_MERCHANT_ACCEPTANCE': 'new',
    'MERCHANT_ACCEPTED': 'accepted',
    'DRIVER_OTW_PICKUP': 'driver_allocated',
    'DRIVER_ARRIVED': 'driver_arrived',
    'PLACED': 'collected',
    'COMPLETED': 'delivered',
    'CANCELLED': 'cancelled',
}
