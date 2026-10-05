{
    'name': 'Account Transfers',
    'depends': ['account_accountant'],
    'description': """
Account Transfers
===========================
A helper model for managing transfers between accounts.
    """,
    'category': 'Accounting/Accounting',
    'data': [
        'data/cron.xml',
        'views/transfer_model_views.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
