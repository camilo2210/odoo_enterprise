{
    'name': 'Uzbekistan - Accounting Reports',
    'description': """
Accounting reports for Uzbekistan
============================================
- Balance Sheet
- Profit and Loss Statement
    """,
    'depends': [
        'account_reports',
        'l10n_uz',
    ],
    'data': [
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
