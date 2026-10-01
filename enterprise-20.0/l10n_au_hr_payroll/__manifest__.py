# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Australia - Payroll",
    "category": "Human Resources/Payroll",
    "countries": ["au"],
    "depends": [
        "hr_payroll",
        "hr_holidays",
        "base_address_extended",
    ],
    'auto_install': ['hr_payroll'],
    "description": """
Australian Payroll Rules.
=========================
""",
    "data": [
        "views/hr_employee_views.xml",
        "views/hr_contract_template_views.xml",
        "views/res_config_settings_views.xml",
        "views/hr_payroll_report.xml",
        "views/hr_payslip_views.xml",
        "views/hr_structure_type_views.xml",
        "views/hr_work_entry_type_views.xml",
        "views/report_payslip_templates.xml",
        "views/l10n_au_super_fund_views.xml",
        "views/l10n_au_super_account_views.xml",
        "views/hr_payslip_run_views.xml",
        "wizards/l10n_au_termination_payment.xml",
        "views/ir_ui_menu.xml",
        "data/resource_calendar_data.xml",
        "data/hr_salary_rule_category_data.xml",
        "data/hr_payroll_structure_type_data.xml",
        "data/hr_payroll_structure_data.xml",
        "data/hr_rule_parameters_data.xml",
        "data/salary_rules/hr_salary_rule_regular_data.xml",
        "data/hr_work_entry_type_data.xml",
        "data/hr_payroll_warning_data.xml",
        "data/res_country_data.xml",
        "data/res.city.csv",
        'security/ir.access.csv',
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_au_hr_payroll/static/src/js/**/*",
        ],
    },
    "demo": [
        "data/l10n_au_hr_payroll_demo.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    'post_init_hook': '_l10n_au_hr_payroll_post_install',
}
