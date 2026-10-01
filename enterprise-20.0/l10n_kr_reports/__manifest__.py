# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Republic of Korea - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Base module for the Republic of Korea reports
    """,
    'depends': [
        'l10n_kr',
        'account_reports',
    ],
    'data': [
        'data/account_return_data.xml',
        'data/tax_report.xml',
        'data/balance_sheet.xml',
        "data/profit_loss.xml",
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'l10n_kr_reports/static/src/components/**/*',
        ],
    },
}
