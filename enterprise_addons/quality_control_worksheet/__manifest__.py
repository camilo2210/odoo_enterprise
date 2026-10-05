# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Worksheet for Quality Control',
    'category': 'Supply Chain/Quality',
    'summary': 'Create custom worksheet for quality control',
    'depends': ['quality_control', 'worksheet'],
    'description': """
Create customizable worksheet for Quality Control.
""",
    "data": [
        'data/quality_control_data.xml',
        'views/quality_views.xml',
        'views/worksheet_template_views.xml',
        'report/worksheet_custom_report_templates.xml',
        'security/ir.access.csv',
    ],
    "demo": [
        'data/quality_worksheet_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'quality_control_worksheet/static/**/*',
        ],
    }
}
