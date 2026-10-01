# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "IoT for Delivery",
    'summary': "Use IoT devices in delivery operations",
    'description': """
Allows using IoT devices, such as scales and printers, for delivery operations.
""",
    'category': 'Supply Chain/Internet of Things (IoT)',
    'depends': ['iot', 'stock_delivery'],
    'data': [
        'wizard/stock_put_in_pack_views.xml',
        'views/iot_device_views.xml',
        'views/stock_picking_views.xml',
        ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'delivery_iot/static/src/**/*',
        ],
    }
}
