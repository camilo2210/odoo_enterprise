# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Vietnam - Payroll',
    'countries': ['vn'],
    'category': 'Human Resources/Payroll',
    'description': """
Vietnamese Payroll Rules
========================
- Compulsory social, health and unemployment insurance (employee and employer shares),
  with the reference level and regional minimum wage floors and ceilings
- Trade union funding (employer) and trade union dues (members)
- Personal income tax: progressive schedule with personal and dependant deductions,
  20% flat rate for non-residents and 10% withholding on casual income
- Overtime and night work paid through premium pays (150% / 200% / 300%, +30%, +20%)
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/resource_calendar_data.xml',
        'data/hr_rule_parameter_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_time_rule_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_template_views.xml',
        'views/payroll_config_settings_views.xml',
    ],
    'demo': [
        'data/l10n_vn_hr_payroll_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_l10n_vn_hr_payroll_post_install',
}
