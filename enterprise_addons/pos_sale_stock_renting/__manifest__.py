# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Point of Sale Rental Stock',
    'category': 'Point of Sale',
    'sequence': 15,
    'summary': "Link between PoS and Stock Rental.",
    'depends': ['pos_sale_stock', 'sale_stock_renting'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_tests': [
            'pos_sale_stock_renting/static/tests/**/*',
        ],
    },
}
