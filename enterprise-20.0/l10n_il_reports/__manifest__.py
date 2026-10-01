{
    'name': 'Israel - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Israel
    """,
    'depends': [
        'l10n_il', 'account_reports'
    ],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': ['l10n_il', 'account_reports'],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
