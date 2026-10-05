# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Point of Sale Subscription',
    'category': 'Point of Sale',
    'sequence': 15,
    'summary': "Link between PoS and Sale Subscription.",
    'depends': ['pos_sale', 'sale_subscription'],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_sale_subscription/static/src/**/*'
        ],
        'web.assets_unit_tests': [
            'pos_sale_subscription/static/tests/unit/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
