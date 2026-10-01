{
    'name': 'PoS & Obox Mobile',
    'category': 'Hidden',
    'depends': ['obox_point_of_sale_android', 'pos_mobile_android'],
    'description': "Obox support of the Point of Sale in the Odoo Mobile App",
    'auto_install': True,
    'data': [
        'views/pos_printer_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'obox_pos_mobile/static/src/app/**/*',
        ],
        'web.assets_backend': [
            'obox_pos_mobile/static/src/backend/**/*',
        ],
        'web.assets_unit_tests': [
            'obox_pos_mobile/static/tests/unit/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
