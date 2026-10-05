# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for rental",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'sale_renting'],
    'data': [
        "data/dashboards.xml",
    ],
    'auto_install': ['sale_renting'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
