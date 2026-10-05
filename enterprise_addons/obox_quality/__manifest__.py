{
    'name': 'Quality Steps & Obox',
    'category': 'Supply Chain/Obox',
    'summary': 'Quality steps and Obox devices',
    'description': """
Base module for quality checks/points using Obox devices.
This module is required for Obox integrations in both Manufacturing
and Quality Control apps.
""",
    'depends': ['obox', 'quality'],
    'data': [
        'views/quality_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
