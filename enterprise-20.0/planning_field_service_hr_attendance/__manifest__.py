{
    'name': "Field Service - Attendance",
    'summary': "Technical Bridge",
    'category': 'Services/Field Service',
    'depends': ['planning_field_service', 'planning_attendance'],
    'assets': {
        'web.assets_backend': [
            'planning_field_service_hr_attendance/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'planning_field_service_hr_attendance/static/tests/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
