# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Dominican Republic - Accounting Reports',
    'description': """
Accounting reports for Dominican Republic
    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': [
        'l10n_do',
        'account_reports',
    ],
    'data': [
        'data/account_return_data.xml',
        'data/profit_and_loss.xml',
        'data/balance_sheet.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_do_reports/static/src/components/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
