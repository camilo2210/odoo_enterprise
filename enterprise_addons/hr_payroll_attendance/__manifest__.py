# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payroll - Attendance',
    'category': 'Human Resources/Employees',
    'sequence': 95,
    'summary': 'Manage extra hours for your hourly paid employees using attendance',
    'auto_install': True,
    'depends': [
        "hr_attendance_gantt",
        'hr_holidays_attendance',
        'hr_payroll',
    ],
    'data': [
        'views/hr_payroll_attendance_views.xml',
        'views/hr_payslip_views.xml',
        'views/res_config_settings_views.xml',
        'data/hr_payroll_attendance_warning_data.xml'
    ],
    'demo': [
        'data/hr_payroll_attendance_demo.xml',
    ],
    'assets': {
        'web.assets_tests': [
            'hr_payroll_attendance/static/tests/tours/**/*'
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
