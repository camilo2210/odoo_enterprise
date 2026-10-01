# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Attendance Gantt",
    'summary': """Gantt view for Attendance""",
    'description': """
    Gantt view for Attendance
    """,
    'category': 'Human Resources/Attendances',
    'depends': ['hr_attendance', 'hr_gantt'],
    'auto_install': True,
    'data': [
        'views/hr_attendance_gantt.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'hr_attendance_gantt/static/src/correct_employee_button/*',
        ],
        'web.assets_backend_lazy': [
            'hr_attendance_gantt/static/src/**/*',
            ('remove', 'hr_attendance_gantt/static/src/correct_employee_button/*'),
        ],
        'web.assets_unit_tests': [
            'hr_attendance_gantt/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
