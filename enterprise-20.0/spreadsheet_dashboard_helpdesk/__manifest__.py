# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for helpdesk",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'helpdesk'],
    'data': [
        "data/dashboards.xml",
    ],
    'auto_install': ['helpdesk'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
