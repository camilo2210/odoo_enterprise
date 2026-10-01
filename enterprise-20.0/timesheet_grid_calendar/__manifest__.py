{
    'name': "Timesheets Calendar",
    'summary': "Add Calendar Events to Timesheets Assistant",
    'description': """
This module allows adding suggestions for calendar events in the Timesheets Assistant.
    """,
    'category': 'Services/Timesheets',
    'depends': ['calendar', 'timesheet_grid'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'timesheet_grid_calendar/static/src/**',
        ],
    },
}
