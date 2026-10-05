# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Easypost Shipping",
    'description': "Send your parcels through Easypost and track them online",
    'category': 'Shipping Connectors',
    'sequence': 315,
    'application': True,
    'depends': ['stock_delivery', 'mail'],
    'data': [
        'views/delivery_carrier_views.xml',
        'wizard/carrier_type_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_easypost/static/src/components/**/*',
        ],
        'web.assets_tests': [
            'delivery_easypost/static/tests/tours/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
