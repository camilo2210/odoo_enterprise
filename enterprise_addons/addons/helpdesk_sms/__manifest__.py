# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Helpdesk - SMS",
    'summary': 'Send text messages when ticket stage move',
    'description': "Send text messages when ticket stage move",
    'category': 'Services/Helpdesk',
    'depends': ['helpdesk', 'sms'],
    'data': [
        'views/helpdesk_stage_views.xml',
        'views/helpdesk_sms_views.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
