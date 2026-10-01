# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Product',
    'category': 'Productivity/Documents',
    'summary': 'Products from Documents',
    'description': """
Adds the ability to create products from the document module and adds the
option to send products' attachments to the documents app.
""",
    'depends': ['documents', 'product'],
    'data': [
        'data/documents_folder_data.xml',
        'data/documents_tag_data.xml',
        'data/res_company_data.xml',
        'views/res_config_settings_views.xml',
        'views/documents_document_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
