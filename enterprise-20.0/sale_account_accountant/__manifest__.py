# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Sale Accounting",
    'category': "Sales/Sales",
    'summary': "Bridge between Sale and Accounting",
    'description': """
Notify that a matching sale order exists in the reconciliation widget.
    """,
    'depends': ['sale', 'account_accountant'],
    'data': [
        'views/sale_order_line_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'sale_account_accountant/static/src/components/**/*',
        ],
    },
}
