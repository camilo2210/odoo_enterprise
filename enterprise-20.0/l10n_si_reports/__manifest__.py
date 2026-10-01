# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Slovenia - Accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """ Base module for Slovenian reports """,
    'depends': [
        'l10n_si',
        'account_reports',
    ],
    'data': [
        'data/ec_sales_lists.xml',
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
        'data/account_return_data.xml',
        'wizard/ec_sales_list_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
