# Part of Odoo. See LICENSE file for full copyright and licensing details
{
    'name': "Helpdesk Field Service",
    'summary': "Allow generating intervention from ticket",
    'description': """
Add intervention from a helpdesk ticket
    """,
    'category': 'Services/Helpdesk',
    'depends': ['helpdesk', 'planning_field_service'],
    'data': [
        'data/mail_message_subtype_data.xml',
        'views/helpdesk_ticket_views.xml',
        'views/planning_slot_views.xml',
    ],
    'demo': ['data/helpdesk_planning_field_service_demo.xml'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
