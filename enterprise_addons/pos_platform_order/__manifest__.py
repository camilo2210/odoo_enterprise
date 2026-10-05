# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Point of Sale - Platform Order Integration',
    'description': """
This module integrates the Odoo Point of Sale with various ordering platforms.
    """,
    'category': 'Sales/Point of Sale',
    'depends': ['pos_enterprise', 'pos_restaurant'],
    'data': [
        'data/platform_order_provider_data.xml',
        'views/platform_order_entity_views.xml',
        'views/platform_order_provider_views.xml',
        'views/platform_order_service_hours_views.xml',
        'views/pos_category_views.xml',
        'views/pos_platform_order_menus.xml',
        'views/product_view.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_platform_order/static/src/app/**/*',
        ],
        'pos_preparation_display.assets': [
            'pos_platform_order/static/src/pos_preparation_display_app/**/*',
        ],
        'web.assets_tests': [
            'pos_platform_order/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_platform_order/static/tests/unit/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
