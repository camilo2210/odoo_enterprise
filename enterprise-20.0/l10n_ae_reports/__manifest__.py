# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'United Arab Emirates - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Accounting reports:
        - Corporate Tax Report
    """,
    'depends': ['l10n_ae', 'account_reports', 'account_fiscal_categories'],
    'data': [
        'data/corporate_tax_report.xml',
        'data/account_return_data.xml',
        'data/actions.xml',
        'data/menuitems.xml',
        'data/account.account.tag.csv',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_ae_reports/static/src/*',
        ],
    },
    'auto_install': ['l10n_ae', 'account_reports', 'account_fiscal_categories'],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
