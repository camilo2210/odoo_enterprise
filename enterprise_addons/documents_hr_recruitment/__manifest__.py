# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Recruitment',
    'category': 'Productivity/Documents',
    'summary': 'Recruitment resumés and letters from documents',
    'description': """
Add the ability to manage resumés and letters from the Documents app.
""",
    'depends': ['documents_hr', 'hr_recruitment'],
    'data': [
        'data/documents_document_data.xml',
        'data/documents_tag_data.xml',
        'data/ir_actions_server_data.xml',
        'data/res_company_data.xml',
        'views/hr_applicant_views.xml',
        'views/hr_job_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
        'data/documents_demo.xml'
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_documents_hr_recruitment_post_init',
}
