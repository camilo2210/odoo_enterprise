# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Bulgaria - Accounting Reports Ledger',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Module for ledger reports
    """,
    'depends': [
        'l10n_bg_reports',
        'l10n_bg_ledger',
    ],
    'data': [
        'data/tax_report.xml',
        'views/res_company_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
