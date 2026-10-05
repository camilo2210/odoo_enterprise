{
    'name': 'PoS & Obox',
    'category': 'Administration/IoT',
    'depends': ['obox', 'point_of_sale'],
    'description': "Link between Obox and Point of Sale",
    'auto_install': True,
    'data': [
        'security/ir.access.csv',
        'views/pos_config_views.xml',
        'views/pos_printer_views.xml',
        'views/obox_queue_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        "point_of_sale._assets_pos": [
            'obox_point_of_sale/static/src/app/**/*',
        ],
        "web.assets_backend": [
            'obox_point_of_sale/static/src/backend/**/*',
        ],
        'web.assets_unit_tests': [
            'obox_point_of_sale/static/tests/unit/**/*',
        ],
        'web.assets_unit_tests_setup': [
            ('remove', 'obox_point_of_sale/static/src/backend/test_obox_printer.js'),  # Causes test errors, can be removed if the base test_epos component is added to unit tests
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
