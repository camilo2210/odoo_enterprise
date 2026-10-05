# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents Project Sign',
    'category': 'Productivity/Documents',
    'summary': 'Sign documents attached to tasks',
    'description': """
Adds an action to sign documents attached to tasks.
""",
    'depends': ['documents_project', 'documents_sign'],
    'data': [
        'data/ir_actions_server_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
