# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Appraisal - Survey',
    'version': '1.2',
    'category': 'Human Resources/Appraisals',
    'sequence': 31,
    'summary': '360 Feedback',
    'website': 'https://www.odoo.com/app/appraisals',
    'depends': ['hr_appraisal', 'survey'],
    'description': """
This module adds an integration with Survey to ask feedbacks to any employee, based on a survey to fill.
    """,
    "data": [
        'wizard/appraisal_ask_feedback_views.xml',
        'wizard/appraisal_select_survey_views.xml',
        'views/hr_appraisal_views.xml',
        'views/hr_appraisal_template_views.xml',
        'views/survey_user_input_views.xml',
        'views/survey_survey_views.xml',
        'views/survey_templates.xml',
        'views/survey_templates_print.xml',
        'views/survey_templates_statistics.xml',
        'data/hr_appraisal_survey_data.xml',
        'data/mail_template_data.xml',
        'data/mail_message_subtype_data.xml',
        'security/ir.access.csv',
    ],
    "demo": [
        'data/hr_appraisal_survey_demo.xml',
    ],
    'other_files': [
        'data/scenarios/scenario_appraisal_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
