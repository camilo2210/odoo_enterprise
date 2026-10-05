# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Nigeria - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting Reports for Nigeria
    """,
    'author': 'Odoo S.A.',
    'depends': [
        'l10n_ng',
        'account_reports',
    ],
    'data': [
        'data/account_return_data.xml',
        'data/tax_report.xml',
    ],
    'auto_install': [
        'l10n_ng',
        'account_reports',
    ],
    'website': 'https://www.odoo.com/app/accounting',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'l10n_ng_reports/static/src/components/**/*',
        ],
    }
}
