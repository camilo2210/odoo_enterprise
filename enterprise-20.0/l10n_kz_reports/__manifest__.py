# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Kazakhstan - Accounting Reports',
    'description': """
Accounting reports for Kazakhstan
Contains Balance sheet, Profit and Loss reports
    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': ['l10n_kz', 'account_reports'],
    'data': [
        'data/account_return_data.xml',
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
