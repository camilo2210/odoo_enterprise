# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale Sale Planning',
    'category': 'Point of Sale',
    'sequence': 15,
    'summary': "Link between PoS and Sale Planning.",
    'depends': ['pos_sale', 'sale_planning', 'pos_planning'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'security/ir.access.csv',
        'views/pos_order_view.xml',
        'views/pos_payment_method_view.xml',
        'views/sale_order_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_sale_planning/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_sale_planning/static/tests/tours/**/*.js',
        ],
        'web.assets_unit_tests': [
            'pos_sale_planning/static/tests/unit/**/*',
        ],
    },
}
