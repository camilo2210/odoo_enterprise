# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Purchase Accounting",
    'category': "Supply Chain/Purchase",
    'summary': "Bridge between Purchase and Accounting",
    'description': """
Add accrued menus and specific filters on purchase order lines for an easier closing process.
    """,
    'depends': ['purchase', 'account_accountant'],
    'data': [
        'views/purchase_order_line_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
