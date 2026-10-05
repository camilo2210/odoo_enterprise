# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'PoS Self Order UrbanPiper',
    'category': 'Sales/Point of Sale',
    'description': """
This module integrates PoS Self-Order and Restaurant modules with UrbanPiper, extending order management
capabilities for orders received through various food delivery platforms.
    """,
    'depends': ['pos_self_order', 'pos_urban_piper'],
    'data': [
        'views/pos_preset_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
