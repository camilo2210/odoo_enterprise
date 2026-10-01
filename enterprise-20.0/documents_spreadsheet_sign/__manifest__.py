{
    'name': 'Spreadsheet Sign',
    'author': 'Odoo S.A.',
    'summary': 'Spreadsheet integration for Sign templates',
    'depends': ['documents_spreadsheet', 'sign'],
    'data': [
        'views/sign_request_views.xml',
    ],
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'documents_spreadsheet_sign/static/src/components/sign_template_custom_cog_menu_patch.js',
            'documents_spreadsheet_sign/static/src/components/sign_template_custom_cog_menu_patch.xml',
        ],
    },
    'license': 'OEEL-1',
}
