# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Lithuania - Payroll',
    'countries': ['lt'],
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll', 'hr_holidays'],
    'auto_install': ['hr_payroll'],
    'description': """
Lithuanian Payroll Rules.
=========================

    * Employee Details
    * Employee Contracts
    * Passport based Contract
    * Allowances/Deductions
    * Allow to configure Basic/Gross/Net Salary
    * Employee Payslip
    * Integrated with Leaves Management
    """,
    'data': [
        'data/resource_calendar_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'views/hr_payroll_report.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_version_views.xml',
        'views/res_config_settings_views.xml',
        'views/report_payslip_templates.xml',
    ],
    'demo': [
        'data/l10n_lt_hr_payroll_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_l10n_lt_hr_payroll_post_install',
}
