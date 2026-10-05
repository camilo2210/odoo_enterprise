# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'CRM Sale Subscription',
    'category': 'Sales/CRM',
    'description': """
Bridge module between CRM and Sale subscription.
    """,
    'depends': ['crm', 'sale_subscription'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
