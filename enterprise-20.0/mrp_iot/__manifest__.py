# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'IoT for Manufacturing',
    'category': 'Supply Chain/Internet of Things (IoT)',
    'summary': 'Extend Manufacturing operations using IoT devices',
    'description': """
This module provides the link between manufacturing and IoT devices.
""",
    'depends': ['mrp_workorder', 'quality_iot'],
    'data': [
        'views/iot_views.xml',
        'views/mrp_workorder_views.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'mrp_iot/static/src/**/*',
        ],
    }
}
