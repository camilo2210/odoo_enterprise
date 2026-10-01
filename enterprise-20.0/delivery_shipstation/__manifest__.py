# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "ShipStation Shipping",
    'description': "Send your parcels through ShipStation and track them online",
    'category': 'Shipping Connectors',
    'application': True,
    'depends': ['stock_delivery'],
    'data': [
        'data/delivery_shipstation.xml',
        'views/delivery_carrier_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_shipstation/static/src/components/**/*.js',
            'delivery_shipstation/static/src/components/**/*.xml',
        ],
        'web.assets_unit_tests': [
            'delivery_shipstation/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
