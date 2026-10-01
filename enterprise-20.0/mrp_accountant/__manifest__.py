# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Mrp Accounting",
    'category': 'Supply Chain/Inventory',
    'summary': "Bridge between Mrp and Accounting",
    'description': """
Automatic accounting for MRP
    """,
    'depends': ['mrp_account', 'stock_accountant'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
