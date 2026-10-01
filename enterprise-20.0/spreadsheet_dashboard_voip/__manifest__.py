# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for Phone",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'voip_hr'],
    'data': [
        "data/dashboards.xml",
    ],
    'auto_install': ['voip_hr'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
