# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Hong Kong - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Accounting reports for Hong Kong
    """,
    'depends': ['l10n_hk', 'account_reports'],
    'auto_install': ['l10n_hk', 'account_reports'],
    'website': 'https://www.odoo.com/app/accounting',
    'data': [
        'data/balance_sheet.xml',
        'data/profit_and_loss.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
