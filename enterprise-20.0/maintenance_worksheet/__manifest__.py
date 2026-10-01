# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Worksheet for Maintenance',
    'category': 'Supply Chain/Maintenance',
    'summary': 'Create custom worksheets for Maintenance',
    'description': """
Create customizable worksheet templates for Maintenance
=======================================================

""",
    'depends': ['maintenance', 'worksheet'],
    'data': [
        'views/maintenance_views.xml',
        'views/maintenance_worksheet_views.xml',
        'report/maintenance_custom_report.xml',
        'report/maintenance_custom_report_templates.xml',
        'security/ir.access.csv',
    ],
    "demo": [
        'data/maintenance_worksheet_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
