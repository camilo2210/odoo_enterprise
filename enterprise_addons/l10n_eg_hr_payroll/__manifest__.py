# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Egypt - Payroll",
    "countries": ["eg"],
    "category": "Human Resources/Payroll",
    "description": """
Egypt Payroll and End of Service rules.
=======================================
- Basic calculation
- End of service calculation
- Other inputs (overtime, salary attachments, etc.)
- Social insurance calculation
- End of service provisions
- Tax break calculations and deductions
- Master payroll export
    """,
    "depends": ["hr_payroll"],
    "auto_install": ["hr_payroll"],
    "data": [
        "data/hr_payroll_warning_data.xml",
        "data/resource_calendar_data.xml",
        "data/hr_rule_parameter_data.xml",
        "data/hr_salary_rule_category_data.xml",
        "data/hr_payroll_structure_type_data.xml",
        "data/hr_work_entry_type_data.xml",
        "data/hr_payroll_structure_data.xml",
        "data/hr_salary_rule_data.xml",
        "wizard/hr_payslip_eg_ytd_adjustment_wizard_views.xml",
        "wizard/l10n_eg_nosi_export_wizard_views.xml",
        "wizard/l10n_eg_nosi_form1_export_wizard_views.xml",
        "wizard/l10n_eg_nosi_form2_export_wizard_views.xml",
        "wizard/l10n_eg_nosi_form6_export_wizard_views.xml",
        "views/hr_contract_template_views.xml",
        "views/hr_employee_views.xml",
        "views/res_config_settings.xml",
        "views/hr_payslip_views.xml",
        'security/ir.access.csv',
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    'post_init_hook': '_l10n_eg_hr_payroll_post_install',
    'uninstall_hook': '_l10n_eg_hr_payroll_uninstall_hook',
    'demo': [
        'data/l10n_eg_hr_payroll_demo.xml',
    ],
}
