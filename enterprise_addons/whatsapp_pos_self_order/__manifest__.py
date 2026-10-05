# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'WhatsApp PoS Self Order',
    'category': 'WhatsApp',
    'description': """Integrates POS Self Order with WhatsApp to send customers order confirmation and receipt.""",
    'depends': ['pos_self_order', 'whatsapp_pos'],
    'data': [
        'data/preset_data.xml',
        'views/pos_preset_views.xml',
    ],
    'assets': {
        'pos_self_order.assets': [
            'whatsapp_pos_self_order/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
