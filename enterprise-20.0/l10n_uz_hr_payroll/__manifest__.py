# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Uzbekistan - Payroll',
    'countries': ['uz'],
    'category': 'Human Resources/Payroll',
    'depends': [
        'hr_payroll',
        'hr_holidays',
    ],
    'auto_install': ['hr_payroll'],
    'data': [
        'views/res_config_settings_view.xml',
        'views/hr_departure_reason_views.xml',
        'views/hr_employee_views.xml',
        'data/resource_calendar_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_rule_parameter_data.xml',
        'data/hr_departure_reason_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
        'wizard/initial_average_wage_update_wizard.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/l10n_uz_hr_payroll_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_l10n_uz_hr_payroll_post_install',
}
