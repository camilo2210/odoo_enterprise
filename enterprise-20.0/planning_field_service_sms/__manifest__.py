# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service - SMS',
    'category': 'Human Resources/Planning',
    'summary':  'Send text messages to notify the status of the intervention',
    'depends': ['planning_field_service', 'sms'],
    'data': [
        'data/planning_field_service_sms_data.xml',
        'views/planning_slot_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
