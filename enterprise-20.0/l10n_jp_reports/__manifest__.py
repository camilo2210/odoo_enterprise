{
    'name': 'Japan - Accounting Reports',
    'description': """
Accounting reports for Japan
============================================
- Corporate tax report
    """,
    'depends': [
        'account_reports',
        'l10n_jp',
    ],
    'data': [
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
