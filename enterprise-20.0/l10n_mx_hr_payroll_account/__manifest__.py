# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Mexico - Payroll with Accounting',
    'author': 'Odoo S.A.',
    'category': 'Human Resources',
    'description': """
Accounting Data for Mexico Payroll Rules
============================================
    """,
    'depends': ['hr_payroll_account', 'l10n_mx', 'l10n_mx_hr_payroll', 'l10n_mx_edi'],
    'data': [
        'security/ir.access.csv',
        'data/ir_cron.xml',
        'data/l10n_mx_hr_payroll_account_data.xml',
        'data/l10n.mx.concept.csv',
        'data/hr_salary_rule_data.xml',
        'data/hr_payroll_warning_data.xml',
        'data/report_paperformat_data.xml',
        'data/4.0/cfdi.xml',
        'data/hr.employee.type.csv',
        'views/hr_payroll_report.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_work_entry_type_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_work_entry_type_views.xml',
        'views/l10n_mx_concept_views.xml',
        'views/report_payslip_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
        'data/l10n_mx_hr_payroll_account_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_mx_hr_payroll_account/static/src/**/*',
            ('remove', 'l10n_mx_hr_payroll_account/static/src/scss/*.scss'),
        ],
        'web.report_assets_common': [
            'l10n_mx_hr_payroll_account/static/src/scss/*.scss',
        ],
    },
    'license': 'OEEL-1',
    'auto_install': ['l10n_mx_hr_payroll', 'hr_payroll_account'],
}
