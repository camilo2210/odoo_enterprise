# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'POS Self-Order / Online Payment / Preparation Display',
    'summary': 'Link between self orders paid online and the preparation display',
    'category': 'Sales/Point of Sale',
    'depends': ['pos_online_payment_self_order', 'pos_enterprise'],
    'auto_install': True,
    'assets': {
        'pos_self_order.assets_tests': [
            'pos_online_payment_self_order_preparation_display/static/tests/**/*',
        ],
        'web.assets_tests': [
            'pos_self_order/static/tests/tours/utils/**',
            'pos_online_payment_self_order_preparation_display/static/tests/tours/online_self_order_kiosk_prep_display.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
