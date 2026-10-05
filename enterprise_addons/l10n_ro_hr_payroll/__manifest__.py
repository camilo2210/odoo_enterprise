# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Romania - Payroll',
    'countries': ['ro'],
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
        'hr_holidays',
    ],
    'auto_install': ['hr_payroll'],
    'data': [
        'views/report_payslip_templates.xml',
        'views/hr_payroll_report.xml',
        'views/hr_version_views.xml',
        'data/resource_calendar_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'demo': [
        'data/l10n_ro_hr_payroll_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_l10n_ro_hr_payroll_post_install',
}
