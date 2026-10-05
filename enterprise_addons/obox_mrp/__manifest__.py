{
    'name': 'Manufacturing & Obox',
    'category': 'Supply Chain/Internet of Things (IoT)',
    'summary': 'Extend Manufacturing operations using Obox devices',
    'description': """
This module provides the link between manufacturing and Obox devices.
""",
    'depends': ['mrp_workorder', 'obox_quality'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'obox_mrp/static/src/**/*',
        ],
    }
}
