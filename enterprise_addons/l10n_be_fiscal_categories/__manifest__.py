# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Fiscal Categories Data',
    'version': '1.1',
    'category': 'Accounting/Accounting',
    'description': """
Fiscal Categories Data for Belgium
    """,
    'depends': [
        'l10n_be',
        'account_fiscal_categories',
    ],
    'data': [
        'data/account_fiscal_categories.xml',
    ],
    'auto_install': True,
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
