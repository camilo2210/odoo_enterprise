{
    'name': 'Quality Control & Obox',
    'category': 'Supply Chain/Obox',
    'summary': 'Control the quality of your products with Obox devices',
    'description': """
Use devices connected to an Obox to control the quality of your products.
""",
    'depends': ['obox_quality', 'quality_control'],
    'data': [
        'wizard/quality_check_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'obox_quality_control/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
