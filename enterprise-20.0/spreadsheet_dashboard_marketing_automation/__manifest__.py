# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for marketing automation",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'marketing_automation'],
    'data': [
        "data/dashboards.xml",
    ],
    'auto_install': ['marketing_automation'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
