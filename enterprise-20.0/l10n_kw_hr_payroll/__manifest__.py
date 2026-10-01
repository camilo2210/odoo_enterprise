# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Kuwait - Payroll',
    'countries': ['kw'],
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'description': """
Kuwait Payroll & Localization
=============================
- Basic setup for Kuwait payroll (Company, Employees, Schedule).
- **Social Insurance:** Kuwaiti Social Security deduction & company contribution rules.
- **End of Service:** EOS Benefit (Indemnity) and Monthly Provision calculations.
- **Leaves & Provisions:** Annual Leave provision and Kuwaiti Sick Leave logic (Tiered deduction).
- Includes "Kuwait: Monthly Pay" salary structure.
    """,
    'data': [
        'data/resource_calendar_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_rule_parameter_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_holiday_accrual_plan_data.xml',

        'views/res_config_settings_views.xml',
        'views/hr_employee_views.xml',
    ],
    'demo': [
        'data/l10n_kw_hr_payroll_demo.xml'
    ],
    'post_init_hook': '_l10n_kw_hr_payroll_post_install',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
