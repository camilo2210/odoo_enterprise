# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Malta - Accounting Reports",
    'category': 'Accounting/Localizations/Reporting',
    "description": """
Malta accounting reports.
====================================================
-Profit and Loss
-Balance Sheet
""",
    "depends": ['l10n_mt', 'account_reports'],
    'data': [
        'data/account_return_data.xml',
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
        'data/account_report_ec_sales_list_report.xml',
        'wizard/ec_sales_list_submission_wizard.xml',
        'wizard/tax_return_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_mt', 'account_reports'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
