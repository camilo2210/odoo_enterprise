{
    'name': 'PoS & Obox Android',
    'category': 'Hidden',
    'depends': ['obox_point_of_sale', 'obox_android'],
    'description': "Point of Sale support for Obox in the Odoo Android app",
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'obox_point_of_sale_android/static/src/app/**/*',
        ],
        'web.assets_unit_tests': [
            'obox_point_of_sale_android/static/tests/unit/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
