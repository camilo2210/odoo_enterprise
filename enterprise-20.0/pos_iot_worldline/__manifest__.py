{
    'name': 'PoS IoT Worldline',
    'category': 'Sales/Point of Sale',
    'summary': 'Integrate your POS with an Worldline payment terminal through IoT',
    'data': [
        'views/pos_payment_method_views.xml',
    ],
    'depends': ['pos_iot'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_iot_worldline/static/src/payment_screen_payment_lines.xml',
        ],
        'point_of_sale.payment_terminals': [
            'pos_iot_worldline/static/src/payment_worldline.js',
        ],
        'web.assets_unit_tests': [
            'pos_iot_worldline/static/tests/unit/**/*',
        ],
    }
}
