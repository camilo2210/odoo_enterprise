# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Quality Steps with IoT',
    'category': 'Supply Chain/Internet of Things (IoT)',
    'summary': 'Quality steps and IoT devices',
    'description': """
Base module for quality checks/points using IoT devices.
This module is required for IoT integrations in both Manufacturing
and Quality Control apps.
""",
    'depends': ['iot', 'quality'],
    'data': [
        'views/iot_device_views.xml',
        'views/quality_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'quality_iot/static/src/**/*',
        ],
    }
}
