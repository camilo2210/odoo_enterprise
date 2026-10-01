# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Tyro',
    'category': 'Sales/Point of Sale',
    'summary': 'Integrate your POS with a Tyro payment terminal (AU)',
    'data': [
        'data/pos_tyro_data.xml',
        'views/pos_payment_method_views.xml',
        'receipt/pos_order_receipt.xml',
    ],
    'depends': ['point_of_sale'],
    'assets': {
        'web.assets_backend': [
            'pos_tyro/static/src/urls.js',
            'pos_tyro/static/src/actions/**/*',
        ],
        'point_of_sale.payment_terminals': [
            'pos_tyro/static/src/urls.js',
            'pos_tyro/static/src/app/**/*',
        ],
        'point_of_sale._assets_pos': [
            'pos_tyro/static/src/overrides/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_tyro/static/tests/unit/data/**/*'
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
