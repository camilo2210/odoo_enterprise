# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Frontdesk - WhatsApp',
    'author': 'Odoo S.A.',
    'summary': 'Send WhatsApp notifications for visitor check-ins',
    'description': """Enable WhatsApp alerts to hosts when visitors check in, or when hosts are unavailable. This bridge module extends Frontdesk with WhatsApp delivery options, using host phone numbers and configurable templates.""",
    'category': 'Human Resources/Frontdesk',
    'depends': ['frontdesk', 'whatsapp'],
    'data': [
        'views/frontdesk_frontdesk_views.xml',
        'data/whatsapp_template_data.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
