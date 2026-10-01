{
    'name': 'North Macedonia - Accounting Reports',
    'description': """
Accounting reports for North Macedonia
============================================
- Balance Sheet
- Profit and Loss Statement
    """,
    'depends': [
        'account_reports',
        'l10n_mk',
    ],
    'data': [
        "data/account_return_data.xml",
        "data/balance_sheet.xml",
        "data/profit_and_loss.xml",
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
