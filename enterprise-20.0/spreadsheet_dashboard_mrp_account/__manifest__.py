# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for manufacturing",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'mrp_account_enterprise'],
    'data': [
        "data/dashboards.xml",
    ],
    'auto_install': ['mrp_account_enterprise'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
