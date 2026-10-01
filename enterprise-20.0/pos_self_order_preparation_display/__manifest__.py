# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'pos self prep display',
    'category': 'Sales/Point of Sale',
    'sequence': 7,
    'depends': ['pos_self_order', 'pos_enterprise'],
    'auto_install': True,
    'assets': {
        'pos_preparation_display.assets': [
            'pos_self_order_preparation_display/static/src/override/pos_preparation_display/**/*',
        ],
        'pos_self_order.assets_tests': [
            'pos_self_order_preparation_display/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
