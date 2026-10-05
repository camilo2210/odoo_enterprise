# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'eCommerce Subscription',
    'category': 'Website/Website',
    'summary': 'Sell subscription products on your eCommerce',
    'description': """
This module allows you to sell subscription products in your eCommerce with
appropriate views and selling choices.
    """,
    'depends': ['website_sale', 'sale_subscription'],
    'data': [
        'data/donation_data.xml',
        'views/templates.xml',
        'views/sale_order_views.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sale_subscription/static/src/js/combo_configurator_dialog/*',
            'sale_subscription/static/src/js/product/*',
            'sale_subscription/static/src/js/product_configurator_dialog/*',
            'website_sale_subscription/static/src/interactions/*',
            'website_sale_subscription/static/src/js/cart_service.js',
            'website_sale_subscription/static/src/xml/donation_snippet.xml',
            'website_sale_subscription/static/src/xml/pricing_view.xml',
        ],
        'web.assets_tests': [
            'website_sale_subscription/static/tests/tours/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
