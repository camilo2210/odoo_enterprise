# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Self Order IoT',
    'category': 'Sales/Point of Sale',
    'summary': 'IoT in PoS Kiosk',
    'depends': ['pos_iot', 'pos_self_order'],
    'auto_install': True,
    "data": [
        "views/iot_box_views.xml",
        "views/res_config_settings.xml",
    ],
    "demo": [
        "demo/iot_demo.xml",
    ],
    'assets': {
        'pos_self_order.assets': [
            'iot/static/src/network_utils/*',
            'pos_iot/static/src/app/utils/printer/iot_printer.js',
            'pos_iot/static/src/overrides/network_utils/iot_http_service.js',
            'point_of_sale/static/src/app/components/popups/select_default_printer_popup/select_default_printer_popup.js',
            'pos_iot/static/src/app/plugins/pos_ticket_printer_plugin.js',
            'pos_self_order_iot/static/src/overrides/models/*',
            'pos_self_order_iot/static/src/overrides/network_utils/*',
        ],
        'pos_self_order.assets_tests': [
            ('include', 'iot.assets_tests'),
            "pos_self_order_iot/static/tests/tours/**/*",
        ],
        'web.assets_unit_tests': [
            'pos_self_order_iot/static/tests/unit/**/*'
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
