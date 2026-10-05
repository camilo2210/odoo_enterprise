# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Türkiye - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Türkiye

- Balance Sheet
- Profit and Loss
    """,
    'depends': [
        'l10n_tr', 'account_reports'
    ],
    'data': [
        'data/account_report_tr_balance_sheet_data.xml',
        'data/account_report_tr_pnl_data.xml',
        'data/account_return_data.xml',
        'data/mail_template_data.xml',
        'views/account_journal_views.xml',
        'views/product_view.xml',
        'views/customer_statement_reconciliation_letter.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_tr_reports/static/src/components/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
