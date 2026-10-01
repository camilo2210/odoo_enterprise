# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Purchase Quality',
    'category': 'Supply Chain/Quality',
    'description': """
Bridge module between Purchase and Quality
    """,
    'depends': [
        'purchase', 'quality_control'
    ],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
