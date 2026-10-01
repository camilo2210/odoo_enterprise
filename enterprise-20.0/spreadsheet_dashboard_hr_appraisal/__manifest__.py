# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard for Employee",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet_dashboard', 'hr_appraisal'],
    'data': [
        "data/dashboards.xml",
    ],
    'auto_install': ['hr_appraisal'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
