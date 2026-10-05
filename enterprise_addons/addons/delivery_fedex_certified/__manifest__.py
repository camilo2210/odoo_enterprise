# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Fedex Shipping",
    'description': "Send your shippings through Fedex and track them online. This version of the FedEx connector is"
                   "compatible with the FedEx REST API available at https://developer.fedex.com/. It is no longer"
                   "compatible with the older FedEx SOAP APIs (which have their own credentials).",
    'category': 'Shipping Connectors',
    'application': True,
    'depends': ['stock_delivery', 'mail'],
    'data': [
        'data/delivery_fedex.xml',
        'data/ir_config_param.xml',
        'security/ir.access.csv',
        'views/delivery_fedex.xml',
        'views/product_views.xml',
        'wizard/account_registration_wizard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_fedex_certified/static/src/js/**/*.js',
            'delivery_fedex_certified/static/src/js/**/*.xml',
            'delivery_fedex_certified/static/src/js/**/*.scss',
            'delivery_fedex_certified/static/src/scss/*.scss',
            ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
