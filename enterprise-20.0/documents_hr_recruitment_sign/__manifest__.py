# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents HR Recruitment Sign',
    'category': 'Productivity/Documents',
    'summary': 'Sign documents attached to Recruitment folders',
    'description': 'Integrates Sign with the Recruitment folder from Documents HR Recruitment.',
    'depends': ['documents_hr_recruitment', 'documents_sign'],
        'data': [
        'data/ir_actions_server_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
