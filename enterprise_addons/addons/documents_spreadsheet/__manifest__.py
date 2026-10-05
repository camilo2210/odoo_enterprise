# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Documents Spreadsheet",
    'category': 'Productivity/Documents',
    'summary': 'Documents Spreadsheet',
    'description': 'Documents Spreadsheet',
    'depends': ['documents', 'spreadsheet_edition', 'base_import'],
    'data': [
        'views/documents_document_views.xml',
        'views/spreadsheet_template_views.xml',
        'views/sharing_templates.xml',
        'views/res_config_settings_views.xml',
        'wizard/documents_sharing_views.xml',
        'wizard/save_spreadsheet_template.xml',
        'wizard/import_to_spreadsheet_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/documents_document_demo.xml'
    ],

    'auto_install': ['documents'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'spreadsheet.o_spreadsheet_core': [
            'documents_spreadsheet/static/src/bundle/**/*.js',
            'documents_spreadsheet/static/src/bundle/**/*.xml',
        ],
        'spreadsheet.public_spreadsheet': [
            ('remove', 'documents_spreadsheet/static/src/bundle/actions/*'),
            ('remove', 'documents_spreadsheet/static/src/bundle/actions/**/*'),
        ],
        'web.assets_backend': [
            'documents_spreadsheet/static/src/core/router.js',
            'documents_spreadsheet/static/src/bundle/**/*.scss',
            'documents_spreadsheet/static/src/documents_view/**/*',
            ('remove', 'documents_spreadsheet/static/src/documents_view/activity/**'),
            'documents_spreadsheet/static/src/spreadsheet_edition/**/*',
            'documents_spreadsheet/static/src/spreadsheet_template/**/*',
            'documents_spreadsheet/static/src/helpers.js',
            'documents_spreadsheet/static/src/spreadsheet_action_loader.js',
            'documents_spreadsheet/static/src/mail/**/*',
            'documents_spreadsheet/static/src/views/**/*',
            'documents_spreadsheet/static/src/editor/**/*',
        ],
        'web.assets_backend_lazy': [
            'documents_spreadsheet/static/src/documents_view/activity/**',
        ],
        'web.assets_tests': [
            'documents_spreadsheet/static/tests/tours/*',
        ],
        'web.assets_unit_tests': [
            'documents_spreadsheet/static/tests/**/*',
        ],
    }
}
