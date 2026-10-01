# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Resellers Commissions For Subscription',
    'category': 'Sales/Commissions',
    'summary': 'Configure resellers commissions on subscription sale',
    'description': """
This module allows to configure commissions for resellers.
    """,
    'depends': [
        'purchase',
        'sale_subscription_partnership',
        'website_crm_partner_assign',
    ],
    'data': [
        'data/data.xml',
        'security/purchase_security.xml',
        'views/account_move_views.xml',
        'views/commission_views.xml',
        'views/purchase_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'report/sale_order_log_report_view.xml',
        'report/sale_subscription_report_view.xml',
        'report/sale_report_view.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
