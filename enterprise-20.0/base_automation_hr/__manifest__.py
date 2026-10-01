# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Automation Rules based on Employee Contracts',
    'category': 'Human Resources',
    'description': """
Bridge to add contract calendar on automation rules
===================================================
    """,
    'depends': ['base_automation', 'hr'],
    'data': [
        'views/base_automation_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
