{
    'name': 'Account Loans Extract',
    'category': 'Accounting/Accounting',
    'depends': ['account_loans', 'account_extract'],
    'summary': 'Extract data from loan scans to fill them automatically',
    'data': [
        'views/res_config_settings_views.xml',
        'views/account_loan_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_loans_extract/static/src/js/*.js',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
