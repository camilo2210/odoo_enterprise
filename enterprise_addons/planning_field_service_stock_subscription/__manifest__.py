# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Stock Subscription',
    'category': 'Human Resources/Planning',
    'summary': 'Manage maintenance contracts with subscriptions',
    'description': """
Manage maintenance contracts with subscriptions
===============================================
""",
    'depends': ['sale_subscription', 'planning_field_service_sale_stock'],
    'data': [
        'security/planning_field_service_security.xml',
        'views/res_config_settings_views.xml',
        'views/planning_slot_views.xml',
        'views/sale_order_views.xml',
        'views/stock_lot_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
