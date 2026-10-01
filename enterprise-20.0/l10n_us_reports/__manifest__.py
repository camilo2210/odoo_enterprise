{
    'name': 'United States - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for US
    """,
    'website': 'https://www.odoo.com/app/accounting',
    'depends': [
        'account_reports',
        'account_reports_cash_basis',
        'l10n_us_account',
    ],
    'data': [
        'data/account_return_data.xml',
        'data/tax_report.xml',
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
    ],
    'auto_install': ['l10n_us_account', 'account_reports'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
