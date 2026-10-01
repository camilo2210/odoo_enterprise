# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Indian Payroll',
    'countries': ['in'],
    'category': 'Human Resources/Payroll',
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'description': """
Indian Payroll Salary Rules.
============================

    -Configuration of hr_payroll for India localization
    -All main contributions rules for India payslip.
    * New payslip report
    * Employee Contracts
    * Allow to configure Basic / Gross / Net Salary
    * Employee PaySlip
    * Allowance / Deduction
    * Integrated with Leaves Management
    * Medical Allowance, Travel Allowance, Child Allowance, ...
    - Payroll Advice and Report
    - Yearly Salary by Employee Report
    """,
    'data': [
        'data/report_paperformat.xml',
        'data/mail_template_data.xml',
        'data/res_country_state_data.xml',
        'views/l10n_in_hr_payroll_report.xml',
        'views/hr_employee_departure_views.xml',
        'data/res_partner_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/salary_rules/hr_salary_rule_stipend_data.xml',
        'data/salary_rules/hr_salary_rule_regular_pay_data.xml',
        'data/hr_employee_type_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/ir_sequence_data.xml',
        'data/hr_payroll_warning_data.xml',
        'views/l10n_in_tax_declaration_history_template.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_employee_public_views.xml',
        'views/res_config_settings_views.xml',
        'views/report_payslip_templates.xml',
        'views/report_payslip_details_template.xml',
        'wizard/hr_salary_register.xml',
        'views/l10n_in_tds_challan_views.xml',
        'views/l10n_in_payroll_form_138_views.xml',
        'views/report_hr_epf_views.xml',
        'views/report_hr_esic_views.xml',
        'wizard/hr_yearly_salary_detail_view.xml',
        'wizard/hr_payroll_payment_report.xml',
        'wizard/l10n_in_labour_welfare_fund_wizard_views.xml',
        'wizard/l10n_in_hr_gratuity_calculation_report_wizard_views.xml',
        'views/report_hr_yearly_salary_detail_template.xml',
        'views/report_payroll_advice_template.xml',
        'views/l10n_in_salary_statement.xml',
        'views/report_l10n_in_salary_statement.xml',
        'views/res_company_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/l10n_in_hr_payroll_demo.xml',
        'data/hr_payroll_structure_type_demo.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_in_hr_payroll/static/src/**/*',
        ],
        'web.report_assets_common': [
            'l10n_in_hr_payroll/static/src/scss/*.scss',
        ],
    },
    'post_init_hook': '_l10n_in_hr_payroll_post_install',
    'uninstall_hook': '_l10n_in_hr_payroll_uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
