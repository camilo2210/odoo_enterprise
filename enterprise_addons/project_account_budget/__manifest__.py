# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Project Budget",
    'summary': "Project account budget",
    'category': 'Services/Project',
    'depends': ['account_budget', 'project_enterprise'],
    'data': [
        'views/project_project_views.xml',
        'views/budget_analytic_views.xml',
        'views/project_update_templates.xml',
    ],
    'demo': [
        'data/budget_analytic_demo.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
