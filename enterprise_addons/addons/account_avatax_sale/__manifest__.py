# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Avatax for SO',
    'category': 'Accounting/Accounting',
    'depends': ['sale_external_tax', 'account_avatax', 'sale'],
    'data': [
        'views/sale_order_views.xml',
        'views/sale_portal_templates.xml',
        'reports/sale_order.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
