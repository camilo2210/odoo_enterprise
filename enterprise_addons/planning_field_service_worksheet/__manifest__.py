# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Reports',
    'category': 'Services/Field Service',
    'summary': 'Create Reports for Field service technicians',
    'description': """
Create Reports for Field Service
================================

""",
    'depends': ['worksheet', 'planning_field_service'],
    'data': [
        "views/planning_field_service_templates.xml",
        "views/planning_slot_template_views.xml",
        "views/planning_slot_views.xml",
        "views/worksheet_template_views.xml",
        'report/report_planning_field_service_intervention_templates.xml',
        'views/planning_field_service_worksheet_menus.xml',
        'views/planning_slot_worksheet_properties_display.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/worksheet_template_demo.xml',
        'data/planning_field_service_worksheet_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'planning_field_service_worksheet/static/src/**/*',
        ],
    },
    'auto_install': True,
    'post_init_hook': 'post_init',
    'uninstall_hook': 'uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
