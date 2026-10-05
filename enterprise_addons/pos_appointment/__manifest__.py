# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale Appointment',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'This module lets you manage online reservations for PoS',
    'website': 'https://www.odoo.com/app/appointments',
    'depends': ['appointment', 'point_of_sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/calendar_event_views.xml',
        'views/appointment_leave_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        # Having the editor add a lot of files to the PoS bundle.
        # We can maybe find a way to have a "light editor" with smaller bundle
        'pos_appointment.html_editor': [
            ('include', 'html_editor.assets_editor'),
            'html_editor/static/src/main/placeholder_plugin.js',
            'html_editor/static/src/backend/**/*',
            'html_editor/static/src/fields/html_field*',

            'web/static/lib/dompurify/DOMpurify.js',
        ],
        'point_of_sale._assets_pos': [
            ('include', 'pos_appointment.html_editor'),
            'web_gantt/static/src/**/*',
            'pos_appointment/static/src/**/*',
            'appointment/static/src/scss/calendar_event_views.scss',
            'appointment/static/src/views/popover/**/*',
            'appointment/static/src/views/gantt/**/*',
            'appointment/static/src/views/kanban/kanban_header.xml',
            'appointment/static/src/views/kanban/kanban_header.js',
            'appointment/static/src/views/kanban/kanban_record.js',
            'appointment/static/src/xml/appointment_svg.xml',
            'calendar/static/src/scss/calendar_event_views.scss',
            'calendar/static/src/views/**/*',
            # Do not display user activities in pos attendee calendar
            ('remove', 'calendar/static/src/views/attendee_calendar/activity/**/*'),
            ('remove', 'calendar/static/src/views/fields/many2many_attendee.js'),
            ('remove', 'calendar/static/src/views/fields/many2many_attendee_expandable.js'),
            ('remove', 'calendar/static/src/views/fields/many2many_attendee_email.js'),
            ('remove', 'web_gantt/static/src/**/*.dark.scss'),
        ],
        'point_of_sale.assets_prod_dark': [
            'web_gantt/static/src/**/*.dark.scss',
        ],
        'web.assets_unit_tests_setup': [
            'web_gantt/static/src/**/*.dark.scss',
            # Adding the files back to be accessible for the tests.
            # Removing them in the _assets_pos bundle also removes them from the prod bundle.
            'calendar/static/src/views/attendee_calendar/activity/**/*',
            'calendar/static/src/views/fields/many2many_attendee.js',
            'calendar/static/src/views/fields/many2many_attendee_expandable.js',
            'calendar/static/src/views/fields/many2many_attendee_email.js',
        ],
        'web.assets_unit_tests': [
            'pos_appointment/static/tests/unit/**/*'
        ],
        'web.assets_tests': [
            'pos_appointment/static/tests/tours/**/*',
        ],
    },
    'uninstall_hook': 'uninstall_hook',
}
