# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'IoT for PoS',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Use IoT Devices in the PoS',
    'description': """
Allows to use in the Point of Sale the devices that are connected to an IoT Box.
Supported devices include payment terminals, receipt printers, scales and customer displays.
""",
    'depends': ['point_of_sale', 'iot'],
    'auto_install': True,
    'uninstall_hook': 'uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'views/iot_box_views.xml',
        'views/iot_device_views.xml',
        'views/pos_config_views.xml',
        'views/pos_printer_views.xml',
        'views/res_config_setting_views.xml',
        'views/pos_payment_method_views.xml',
        'wizard/auto_config_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'iot/static/src/network_utils/*',
            'printer/static/src/print_action_handler.js',
            'printer/static/src/services/report_printers_cache.js',
            'iot/static/src/iot_report_action.js',
            'printer/static/src/wizard/select_printers_wizard.js',
            'pos_iot/static/src/**/*',
            ('remove', 'pos_iot/static/src/backend/**/*'),
        ],
        'point_of_sale.payment_terminals': [
            'pos_iot/static/src/app/utils/payment/payment_interface_iot.js',
        ],
        'web.assets_tests': [
            'pos_iot/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_iot/static/tests/unit/**/*'
        ],
        'web.assets_backend': [
            'pos_iot/static/src/backend/**/*',
        ],
    }
}
