# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Sendcloud Shipping",
    'description': "Shipping Integration with Sendcloud platform",
    'category': 'Shipping Connectors',
    'sequence': 316,
    'application': True,
    'depends': ['stock_delivery', 'mail'],
    'data': [
        'data/mail_templates.xml',
        'views/delivery_carrier_views.xml',
        'wizard/sendcloud_shipping_wizard.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_sendcloud/static/src/**/*.js',
            'delivery_sendcloud/static/src/**/*.xml',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
