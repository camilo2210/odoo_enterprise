# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Project Payroll Accounting',
    'category': 'Services/payroll/account',
    'summary': 'Project payroll accounting',
    'description': 'Bridge created to add the number of contracts linked to an AA to a project form',
    'depends': ['project', 'hr_payroll_account'],
    'data': [
        'views/project_project_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
