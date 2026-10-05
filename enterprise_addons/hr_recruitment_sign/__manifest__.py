# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Recruitment - Signature',
    'category': 'Human Resources/Recruitment',
    'summary': 'Manage the signatures to send to your applicants',
    'depends': ['hr_recruitment', 'hr_sign'],
    'data': [
        'security/res_groups.xml',
        'data/mail_templates_chatter.xml',
        'wizard/hr_recruitment_sign_document_wizard_view.xml',
        'views/hr_applicant_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_tests': [
            'hr_recruitment_sign/static/tests/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
