# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Payroll',
    'category': 'Productivity/Documents',
    'summary': 'Store employee payslips in the Document app',
    'description': """
Employee payslips will be automatically integrated to the Document app.
""",
    'depends': ['documents_hr', 'hr_payroll'],
    'data': [
        'data/mail_template_data.xml',
        'data/ir_action_server_data.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payroll_employee_declaration_views.xml',
        'views/res_config_settings_views.xml',
        'data/hr_payroll_warning_data.xml',
        'wizard/payslip_send_mail_views.xml',
        'wizard/payroll_overwrite_employee_declaration_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'documents_hr_payroll/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_documents_hr_payroll_post_init',
}
