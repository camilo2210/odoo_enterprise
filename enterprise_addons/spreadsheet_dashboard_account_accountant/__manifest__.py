# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for accounting",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'accountant'],
    'data': [
        "data/dashboards.xml",
    ],
    'auto_install': ['accountant'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
