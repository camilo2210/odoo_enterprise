# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Approvals',
    'category': 'Productivity/Documents',
    'summary': 'Approval from documents',
    'description': """
Adds approvals data to documents
""",
    'depends': ['documents', 'approvals'],
    'data': [
        "views/res_config_settings_views.xml",
        "views/approval_request_views.xml",
        "data/documents_folder_data.xml",
        "data/res_company_data.xml"
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_documents_approval_post_init',
}
