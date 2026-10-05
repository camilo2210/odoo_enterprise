# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Starshipit Shipping",
    'description': """
Send your shippings through Starshipit and track them online
============================================================

Starshipit is the leading provider of integrated shipping and tracking solutions for growing e-commerce businesses.
Seamlessly integrating with a large range of couriers and platforms,
you can streamline every step of your fulfilment process,
reduce handling time and improve customer experience.
    """,
    'category': 'Shipping Connectors',
    'application': True,
    'depends': ['stock_delivery'],
    'data': [
        'data/ir_cron_data.xml',
        'views/delivery_carrier_views.xml',
        'views/stock_picking_views.xml',
        'wizard/starshipit_shipping_wizard.xml',
        'wizard/choose_delivery_carrier_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_starshipit/static/src/components/**/*.js',
            'delivery_starshipit/static/src/components/**/*.xml',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
