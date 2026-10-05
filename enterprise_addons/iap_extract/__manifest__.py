# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Iap Extract',
    'category': 'Hidden/Tools',
    'summary': 'Common module for requesting data from the extract server',
    'depends': ['base', 'iap', 'mail', 'iap_mail'],
    'data': [
        'data/config_parameter_endpoint.xml',
        'data/iap_service_data.xml',
        'data/mail_template_data.xml',
    ],
    'auto_install': True,
    'iap_paid_service': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'iap_extract/static/src/components/**/*',
        ],
        'web.assets_unit_tests': [
            'iap_extract/static/tests/**/*',
        ],
    }
}
