# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Appraisals',
    'version': '1.2',
    'category': 'Human Resources/Appraisals',
    'sequence': 180,
    'summary': 'Assess your employees',
    'website': 'https://www.odoo.com/app/appraisals',
    'depends': ['calendar', 'hr_gantt'],
    'description': """
Periodical Employees appraisal
==============================

By using this application you can maintain the motivational process by doing periodical appraisals of your employees performance. The regular assessment of human resources can benefit your people as well your organization.

An appraisal plan can be assigned to each employee. These plans define the frequency and the way you manage your periodic personal appraisal.

Key Features
------------
* Ability to create employee's appraisal(s).
* An appraisal can be created by an employee's manager or automatically based on schedule which is defined in the employee form.
* The appraisal is done according to a plan in which various surveys can be created. Each survey can be answered by a particular level in the employees hierarchy. The final review and appraisal is done by the manager.
* Manager, colleague, collaborator, and employee himself/herself receives email to perform a periodical appraisal.
* Every Appraisal Form filled by employees, colleague, collaborator, can be viewed in a PDF form.
* Meeting Requests are created manually according to employees appraisals.
""",
    "data": [
        'security/hr_appraisal_security.xml',
        'wizard/request_appraisal_views.xml',
        'data/hr_appraisal_templates.xml',
        'views/mail_activity_plan_views.xml',
        'views/mail_activity_views.xml',
        'views/hr_appraisal_views.xml',
        'views/hr_appraisal_goal_template_views.xml',
        'views/hr_appraisal_goal_views.xml',
        'views/hr_appraisal_note_views.xml',
        'views/hr_department_views.xml',
        'views/res_config_settings_view.xml',
        'views/hr_employee_views.xml',
        'views/hr_employee_public_views.xml',
        'views/hr_appraisal_template_views.xml',
        'data/hr_appraisal_data.xml',
        'data/mail_template_data.xml',
        'wizard/hr_appraisal_campaign_wizard.xml',
        'views/hr_job_views.xml',
        'security/ir.access.csv',
    ],
    "demo": [
        "data/hr_appraisal_demo.xml",
    ],
    'other_files': [
        'data/scenarios/hr_appraisal_scenario.xml',
    ],
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_generate_assessment_note_ids',
    'assets': {
        'web.assets_backend': [
            'hr_appraisal/static/src/**/*',
            ('remove', 'hr_appraisal/static/src/views/gantt/**/*'),
        ],
        # we need to lazy load gantt views to be able to use web_gantt's classes
        'web.assets_backend_lazy': [
            'hr_appraisal/static/src/views/gantt/**/*',
        ],
        'web.assets_tests': [
            'hr_appraisal/static/tests/tours/*.js',
        ]
    }
}
