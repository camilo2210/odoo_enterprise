{
    'name': 'PoS Stock enterprise',
    'category': 'Sales/Point of Sale',
    'depends': ['pos_enterprise', 'pos_stock'],
    'summary': 'Stock integration for advanced PoS features',
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'pos_preparation_display.assets': [
            'pos_stock_enterprise/static/src/**/*',
        ],
        'pos_preparation_display.assets_tour_tests': [
            ("include", "point_of_sale.base_tests"),
            "pos_stock_enterprise/static/tests/tours/preparation_display/**/*"
        ],
        'web.assets_tests': [
            'pos_stock_enterprise/static/tests/tours/point_of_sale/**/*',
        ],
    },
}
