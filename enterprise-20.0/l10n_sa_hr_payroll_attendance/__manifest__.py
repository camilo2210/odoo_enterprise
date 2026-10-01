# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Saudi Arabia Payroll - Attendance',
    'author': 'Odoo S.A.',
    'category': 'Human Resources/Employees',
    'summary': 'Manage late attendance for your employees for saudi arabia payroll',
    'license': 'OEEL-1',
    'depends': [
        'hr_payroll_attendance',
        'l10n_sa_hr_payroll',
    ],
    'data': [
        'data/hr_salary_rule_saudi_data.xml',
        'views/res_config_settings_views.xml',
        'views/hr_attendance_view.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_sa_hr_payroll_attendance/static/src/**/*',
        ],
    },
    'auto_install': True,
}
