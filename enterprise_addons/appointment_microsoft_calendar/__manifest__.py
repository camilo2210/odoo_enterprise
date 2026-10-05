# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Appointment Microsoft Calendar',
    'category': 'Productivity',
    'description': """Allow to sync your Outlook Calendar from the Appointment App""",
    'depends': ['microsoft_calendar', 'appointment'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'views/appointment_type_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
          'appointment_microsoft_calendar/static/src/**/*',
        ],
    },
    'auto_install': True,
}
