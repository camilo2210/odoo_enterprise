{
    'name': "Intercompany Payment - Accountant",
    'category': 'Accounting/Accounting',
    'summary': "Allow to have Inter company payment in the bank reconciliation widget",
    'depends': ['account_payment_interco', 'account_accountant'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
         'views/account_bank_statement_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_accountant_payment_interco/static/src/components/**/*',
        ],
    },
}
