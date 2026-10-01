# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Greece - Accounting Reports',
    'description': """
Accounting reports for Greece
================================

    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': [
        'l10n_gr',
        'account_reports',
    ],
    'data': [
        'data/ec_sales_list_report-gr.xml',
        'data/account_return_data.xml',
        'data/balance_sheet-gr.xml',
        'data/profit_and_loss-gr.xml',
        'wizard/ec_sales_list_submission_wizard.xml',
        'wizard/tax_return_type_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_gr', 'account_reports'],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
