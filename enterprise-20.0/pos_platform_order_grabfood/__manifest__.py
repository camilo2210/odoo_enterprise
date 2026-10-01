# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Platform Order Provider: GrabFood',
    'category': 'Sales/Point of Sale',
    'description': """
This module integrates with GrabFood to receive and manage orders.
    """,
    'depends': ['pos_platform_order'],
    'data': [
        'data/platform_order_provider_data.xml',
        'views/platform_order_provider_views.xml',
    ],
    'external_dependencies': {
        'python': ['pyjwt'],
        'apt': {
            'pyjwt': 'python3-jwt',
        },
    },
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_platform_order_grabfood/static/src/app/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
