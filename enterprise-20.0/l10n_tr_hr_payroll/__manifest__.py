# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Türkiye - Payroll',
    'countries': ['tr'],
    'category': 'Human Resources/Payroll',
    'description': """
Türkiye Payroll and Tax Rules
=============================
- Social Security Premium/Insurance calculations for employment and unemployment
- Income tax calculations
- Stamp tax deductions
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/resource_calendar_data.xml',
        'data/hr_rule_parameter_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_salary_rule_advance_pay_data.xml',
        'data/hr_payroll_warning_data.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings.xml',
        'views/l10n_tr_sgk_hiring_notice_template.xml',
        'views/res_config_settings_views.xml',
        'wizard/l10n_tr_sgk_hiring_wizard_views.xml',
        'views/menuitems.xml',
        'report/report_hr_employee_employment_certificate.xml',
        'report/report_hr_employee_employment_certificate_template.xml',
        'data/muhsgk_v2_template.xml',
        'views/hr_payroll_structure_views.xml',
        "views/hr_payslip_views.xml",
        'wizard/hr_payroll_report_wizard.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'demo': [
        'data/l10n_tr_hr_payroll_demo.xml',
    ],
    'post_init_hook': '_l10n_tr_hr_payroll_post_install',
    'uninstall_hook': '_l10n_tr_hr_payroll_uninstall_hook',
}
