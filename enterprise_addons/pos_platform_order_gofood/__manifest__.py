# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Platform Order Provider: GoFood',
    'category': 'Sales/Point of Sale',
    'description': """
This module integrates with GoFood to receive and manage orders.
    """,
    'depends': ['pos_platform_order'],
    'data': [
        'data/platform_order_provider_data.xml',
        'views/platform_order_provider_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_platform_order_gofood/static/src/app/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
