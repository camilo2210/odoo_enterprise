# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Stock Accounting",
    'category': 'Supply Chain/Inventory',
    'summary': "Bridge between Stock and Accounting",
    'description': """
Filters the stock lines out of the reconciliation widget
    """,
    'depends': ['stock_account', 'account_accountant', 'account_reports'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
