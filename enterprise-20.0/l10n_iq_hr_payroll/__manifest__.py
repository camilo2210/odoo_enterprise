# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Iraq - Payroll',
    'countries': ['iq'],
    'category': 'Human Resources/Payroll',
    'author': 'Odoo S.A.',
    'description': """
Iraqi Payroll and Tax Rules
========================================

- Social Insurance computation.
- End of Service benefit and Provisions.
- Leaves Setup.
- Overtime Ruleset.
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/hr_work_entry_type_data.xml',
        'data/resource_calendar_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_rule_parameter_data.xml',
        'data/hr_departure_reason_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_holiday_accrual_plan_data.xml',

        'views/res_config_settings_view.xml',
        'views/hr_employee_views.xml',
    ],
    'post_init_hook': '_l10n_iq_hr_payroll_post_install',
    'license': 'OEEL-1',
    'demo': [
        'data/l10n_iq_hr_payroll_demo.xml',
    ],
}
