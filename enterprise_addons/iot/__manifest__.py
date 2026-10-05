# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Internet of Things',
    'category': 'Administration/IoT',
    'sequence': 250,
    'summary': 'Basic models and helpers to support Internet of Things.',
    'description': """
This module provides management of your IoT Boxes inside Odoo.
""",
    'website': 'https://www.odoo.com/app/iot',
    'depends': ['printer', 'mail', 'web'],
    'data': [
        'wizard/add_iot_box_views.xml',
        'wizard/select_printers_wizard.xml',
        'security/iot_security.xml',
        'views/iot_menus.xml',
        'views/iot_box_views.xml',
        'views/iot_device_views.xml',
        'views/ir_actions_report.xml',
        'views/printer_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/iot_demo.xml'
    ],
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'iot/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'iot/static/src/network_utils/iot_websocket.js',
            'iot/static/tests/unit/**/*',
        ],
        'web.assets_tests': [
            ('include', 'iot.assets_tests'),
        ],
        'iot.assets_tests': [
            'iot/static/tests/tours/**/*',
        ],
    }
}
