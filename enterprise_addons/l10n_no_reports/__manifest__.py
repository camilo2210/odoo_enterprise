# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Norway - Accounting Reports',
    'version': '1.1',
    'description': """
Accounting reports for Norway
================================

    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': ['l10n_no', 'account_reports'],
    'data': [
        'data/account_return_data.xml',
        'data/profit_loss.xml',
        'data/balance_sheet.xml',
        'data/tax_report.xml',
        'data/tax_report_export.xml',
        'wizard/vat_report_export.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_no', 'account_reports'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
