# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Jordan - Payroll',
    'countries': ['jo'],
    'category': 'Human Resources/Payroll',
    'author': 'Odoo S.A., Flex Ops',
    'description': """
Jordanian Payroll and Tax Rules
========================================

- Overtime Computations.
- End of Service benefit and remaining leaves compensation rules.
- Provisions for End of service benefit and annual leaves.
- Income tax withholding and exemptions.
- Sick leaves deductions.
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        "data/resource_calendar_data.xml",
        'data/hr_rule_parameter_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_contract_template_views.xml',
        'views/res_config_settings_view.xml',
        'views/hr_employee_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'demo': [
        'data/l10n_jo_hr_payroll_demo.xml',
    ],
    'post_init_hook': '_l10n_jo_hr_payroll_post_install',
}
