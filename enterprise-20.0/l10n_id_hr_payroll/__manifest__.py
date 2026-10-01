# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Indonesia - Payroll',
    'countries': ['id'],
    'category': 'Human Resources/Payroll',
    'description': """
        Indonesia Payroll Rules.
    """,
    'depends': [
        'hr_payroll',
        'hr_holidays',
    ],
    'auto_install': ['hr_payroll'],
    'data': [
        "data/resource_calendar_data.xml",
        "data/hr_employee_type_data.xml",
        "data/hr_payroll_structure_type_data.xml",
        "data/hr_payroll_structure_data.xml",
        "data/hr_salary_rule_category_data.xml",
        "data/hr_rule_parameter_data.xml",
        "data/hr_salary_rule_data.xml",
        "data/hr_work_entry_type_data.xml",
        "views/hr_employee_views.xml",
        "views/hr_contract_template_views.xml",
        "views/res_config_settings_views.xml",
        "views/hr_payslip_views.xml",
        "views/hr_payslip_line_views.xml",
        "views/report_payslip_templates.xml",
        "views/hr_payroll_report.xml",
    ],
    'demo': [
        "data/l10n_id_hr_payroll_demo.xml"
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_l10n_id_hr_payroll_post_install',
}
