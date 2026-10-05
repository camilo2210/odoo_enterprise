# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Accounting',
    'category': 'Productivity/Documents',
    'summary': 'Invoices from Documents',
    'description': """
Bridge module between the accounting and documents apps. It enables
the creation invoices from the Documents module, and adds a
button on Accounting's reports allowing to save the report into the
Documents app in the desired format(s).
""",
    'depends': ['documents', 'account_reports'],
    'data': [
        'data/documents_account_tour.xml',
        'data/ir_actions_server_data.xml',
        'views/account_move_views.xml',
        'views/documents_account_folder_setting_views.xml',
        'views/documents_document_views.xml',
        'views/ir_actions_server_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/account_reports_export_wizard_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/documents_account_demo.xml',
    ],
    'other_files': [
        'demo/files/ready_mat.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'documents_account/static/src/**/*',
            ('remove', 'documents_account/static/src/views/activity/**'),
        ],
        'web.assets_backend_lazy': [
            'documents_account/static/src/views/activity/**',
        ],
        'web.assets_tests': [
            'documents_account/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'documents_account/static/tests/**/*',
            ('remove', 'documents_account/static/tests/tours/**/*'),
            ('remove', 'documents_account/static/tests/assets/**/*'),
        ],
    },
    'post_init_hook': '_documents_account_post_init',
}
