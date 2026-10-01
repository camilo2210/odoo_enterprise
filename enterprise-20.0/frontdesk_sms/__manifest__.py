# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Frontdesk - SMS',
    'author': 'Odoo S.A.',
    'summary': 'Send SMS notifications for visitor check-ins',
    'description': """Enable SMS alerts to hosts when visitors check in, or when hosts are unavailable. This bridge module extends Frontdesk with SMS delivery options, using host phone numbers and configurable templates.""",
    'category': 'Human Resources/Frontdesk',
    'depends': ['frontdesk', 'sms'],
    'data': [
        'views/frontdesk_frontdesk_views.xml',
        'data/sms_template_data.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
