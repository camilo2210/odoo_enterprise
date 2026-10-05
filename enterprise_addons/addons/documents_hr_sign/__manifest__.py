# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Contract - Signature',
    'category': 'Productivity/Documents',
    'summary': 'Manage employee documents requiring signature',
    'description': """
This module extends the Documents app to manage employee documents requiring signature.
It integrates with the HR Sign module to facilitate the signing process of employee contracts and other HR-related documents.
    """,
    'depends': ['documents_hr', 'hr_sign', 'documents_sign'],
    'data': [
        'data/documents_tag_data.xml',
    ],
    'post_init_hook': '_embed_sign_post_init',
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
