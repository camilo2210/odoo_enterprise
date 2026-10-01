{
    'name': "Timesheets Grid / Attendance",
    'summary': "Bridge module between Timesheets Grid and Attendance",
    'description': """
Bridge module for Timesheets Grid and HR Attendance
====================================================
This module modifies the timesheet systray behavior when the attendance module is installed,
allowing for integrated attendance and timesheet tracking from a single interface.
    """,
    'category': 'Hidden',
    'depends': ['timesheet_grid', 'hr_attendance'],
    'assets': {
        'web.assets_backend': [
            'timesheet_grid_hr_attendance/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'timesheet_grid_hr_attendance/static/tests/**/*.test.js',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
