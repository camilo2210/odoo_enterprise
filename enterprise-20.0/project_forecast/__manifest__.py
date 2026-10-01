# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Project Planning",
    'summary': """Plan your resources on project tasks""",
    'description': """
Schedule your teams across projects and estimate deadlines more accurately.
    """,
    'category': 'Services/Project',
    'depends': ['project', 'planning', 'web_grid'],
    'demo': [
        'data/planning_role_demo.xml',
        'data/planning_slot_template_demo.xml',
        'data/planning_slot_demo.xml',
    ],
    'data': [
        'security/project_forecast_security.xml',
        'views/planning_slot_template_views.xml',
        'views/planning_slot_templates.xml',
        'views/planning_slot_views.xml',
        'views/project_project_views.xml',
        'views/project_task_views.xml',
        'views/planning_menus.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'uninstall_hook': '_uninstall_hook',
    'assets': {
        'web.assets_backend_lazy': [
            'project_forecast/static/src/views/**/*',
        ],
        'web.assets_unit_tests': [
            'project_forecast/static/tests/**/*',
        ],
        'web.assets_tests': [
            'project_forecast/static/tests/tours/*',
        ],
    }
}
