# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Signatures',
    'category': 'Productivity/Documents',
    'summary': 'Signature templates from Documents',
    'description': """
Add the ability to create signatures from the document module.
The first element of the selection (in DRM) will be used as the signature attachment.
""",
    'depends': ['documents', 'sign'],

    'data': [
        'data/documents_folder_data.xml',
        'data/ir_action_server_data.xml',
        'views/sign_templates.xml',
        'views/res_config_settings.xml',
        'wizard/sign_import_documents.xml',
        'wizard/sign_send_request_views.xml',

        'security/ir.access.csv',
    ],

    'demo': [
        'demo/documents_document_demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'documents_sign/static/src/backend_components/**/*',
        ],
    },
    'post_init_hook': '_post_init_hook',
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
