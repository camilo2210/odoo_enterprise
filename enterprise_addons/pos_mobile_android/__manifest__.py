{
    'name': 'Point of Sale Mobile Android',
    'category': 'Hidden',
    'summary': 'Odoo Android app features for the Point of Sale',
    'description': """
Point of Sale features of the Odoo Android app: native bridge, local network
requests and home screen shortcuts.
        """,
    'depends': ['pos_mobile'],
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'pos_mobile_android/static/src/app/utils/native.js',
        ],
        'point_of_sale._assets_pos': [
            'pos_mobile_android/static/src/app/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_mobile_android/static/tests/unit/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
