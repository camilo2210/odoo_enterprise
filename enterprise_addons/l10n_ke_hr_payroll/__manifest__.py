# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Kenya - Payroll',
    'countries': ['ke'],
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll', 'hr_holidays'],
    'auto_install': True,
    'description': """
Kenyan Payroll Rules.
=====================

    * Employee Details
    * Employee Contracts
    * Allowances/Deductions
    * Allow to configure Basic/Gross/Net Salary
    * Employee Payslip
    * Integrated with Leaves Management
    """,
    'data': [
        'data/report_paperformat_data.xml',
        'data/resource_calendar_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_work_entry_type_data.xml',
        'wizards/l10n_ke_hr_payroll_nssf_report_wizard_views.xml',
        'wizards/l10n_ke_hr_payroll_shif_report_wizard_views.xml',
        'views/hr_payroll_report.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_employee_views.xml',
        'views/l10n_ke_tax_deduction_card_views.xml',
        'views/report_payslip_templates.xml',
        'views/res_company_views.xml',
        'views/l10n_ke_hr_payroll_menus.xml',
        'report/l10n_ke_tax_reduction_card_templates.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.report_assets_common': [
            'l10n_ke_hr_payroll/static/src/**/*',
        ],
    },
    'demo': [
        'data/l10n_ke_hr_payroll_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'post_init_hook': '_l10n_ke_hr_payroll_post_install',
}
