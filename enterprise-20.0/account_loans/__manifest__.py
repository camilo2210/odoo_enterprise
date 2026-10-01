{
    'name': 'Loans Management',
    'description': """
Loans management
=================
Keeps track of loans, and creates corresponding journal entries.
    """,
    'category': 'Accounting/Accounting',
    'sequence': 32,
    'depends': ['account_asset', 'base_import'],
    'data': [

        'wizard/account_loan_close_wizard.xml',
        'wizard/account_loan_compute_wizard.xml',

        'views/account_asset_views.xml',
        'views/account_asset_group_views.xml',
        'views/account_loan_views.xml',
        'views/account_move_views.xml',

        'data/account_return_check_template.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/account_loans_demo.xml',
    ],
    'other_files': [
        'demo/files/loan_amortization_demo.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'account_loans/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'account_loans/static/tests/*',
        ],
    }
}
