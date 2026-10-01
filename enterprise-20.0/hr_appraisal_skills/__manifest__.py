# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Appraisal - Skills",
    'category': 'Human Resources/Appraisals',
    'sequence': 280,
    'summary': 'Manage skills of your employees during an appraisal process',

    'description': """
This module makes it possible to manage employee skills during an appraisal process.
    """,
    'depends': ['hr_appraisal', 'hr_skills'],
    'data': [
        'views/hr_skills_views.xml',
        'views/hr_appraisal_goal_template_views.xml',
        'views/hr_appraisal_goal_template_skill_views.xml',
        'views/hr_appraisal_skill_views.xml',
        'views/hr_appraisal_skills_templates.xml',
        'views/hr_appraisal_goal_views.xml',
        'report/hr_appraisal_skill_evolution_report_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/hr_appraisal_skills_demo.xml',
    ],
    'other_files': [
        'demo/scenarios/scenario_appraisal_demo.xml',
    ],
    'auto_install': True,
    'post_init_hook': '_populate_skills_for_confirmed',
    'assets': {
        'web.assets_backend': [
            'hr_appraisal_skills/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
