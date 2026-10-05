{
    'name': 'Taiwan - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Taiwan
================================
    """,
    'depends': [
        'l10n_tw',
        'account_reports'
    ],
    'data': [
        'data/profit_and_loss.xml',
        'data/balance_sheet.xml',
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
