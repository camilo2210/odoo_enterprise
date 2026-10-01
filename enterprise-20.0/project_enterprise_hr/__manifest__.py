# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Project Enterprise HR",
    'version': '1.1',
    'summary': """Bridge module for project_enterprise and hr""",
    'description': """
Bridge module for project_enterprise and hr
    """,
    'category': 'Services/Project',
    'depends': ['project_enterprise', 'hr'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend_lazy': [
            'project_enterprise_hr/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'project_enterprise_hr/static/tests/**/*',
        ],
    },
}
