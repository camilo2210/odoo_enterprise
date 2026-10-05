# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS IoT Six',
    'category': 'Sales/Point Of Sale',
    'summary': 'Integrate your POS with a Six payment terminal through IoT',
    'data': [
        'views/pos_payment_method_views.xml',
        'views/iot_box_views.xml',
        'receipt/pos_six_balance_receipt.xml',
    ],
    'depends': ['pos_iot'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_iot_six/static/src/js/balance_button.js',
            'pos_iot_six/static/src/xml/balance_button.xml',
        ],
        'point_of_sale.payment_terminals': [
            'pos_iot_six/static/src/js/payment_six.js',
        ],
        'web.assets_backend': [
            'pos_iot_six/static/src/js/six_terminal_id_field.*',
            'pos_iot_six/static/src/css/six_terminal_id_field.css',
        ],
        'web.assets_unit_tests': [
            'pos_iot_six/static/tests/unit/**/*',
        ],
    }
}
