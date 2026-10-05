# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Croatia - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Croatia
    """,
    'depends': [
        'l10n_hr', 'account_reports'
    ],
    'data': [
        'data/account_return_data.xml',
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
        'data/account_report_ec_sales_list_report.xml',
        'wizard/ec_sales_list_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_hr', 'account_reports'],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
