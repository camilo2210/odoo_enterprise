# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'South Africa - Payroll',
    'countries': ['za'],
    'category': 'Human Resources/Payroll',
    'description': """
South Africa Payroll Rules.
============================

    * Employee Details
    * Employee Contracts
    * Allowances/Deductions
    * Allow to configure Basic/Gross/Net Salary
    * Employee Payslip
    * Integrated with Leaves Management
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/resource_calendar_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_work_entry_type_data.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings.xml',
    ],
    'demo': [
        'data/l10n_za_hr_payroll_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_l10n_za_hr_payroll_post_install',
}
