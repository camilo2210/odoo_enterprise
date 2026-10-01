# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'United Arab Emirates - Payroll',
    'author': 'Odoo S.A.',
    'countries': ['ae'],
    'category': 'Human Resources/Payroll',
    'description': """
United Arab Emirates Payroll and End of Service rules.
=======================================================
- Basic salary calculations
- EOS calculations
- Provisions for annual leaves and end of service benefit
- Social insurance rules for locals
- Overtime rule for the other inputs case
- Sick-leaves calculations
- DEWS benefit computation
- Calculation for unused leaves for EOS calculation
- Additional other input rules for (bonus, commissions, arrears, etc.)
- WPS
    """,
    'depends': ['hr_payroll', 'hr_holidays'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/resource_calendar_data.xml',
        "data/hr_holiday_accrual_plan_data.xml",
        "data/mail_activity_type_data.xml",
        'views/hr_job_views.xml',
        'views/hr_payroll_report.xml',
        'views/report_payslip_templates.xml',
        'views/menuitems.xml',
        'data/emiratization_target_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_salary_rule_regular_pay_data.xml',
        'data/hr_salary_rule_instant_pay_data.xml',
        'data/hr_work_entry_type_data.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_payslip_run_views.xml',
        'data/hr_rule_parameter_data.xml',
        'views/res_config_settings_view.xml',
        'wizard/hr_payroll_payment_report_wizard.xml',
        'wizard/l10n_ae_eos_benefit_wizard.xml',
        'report/report_hr_employee_salary_certificate_template.xml',
        'report/report_hr_employee_salary_certificate.xml',
        'views/emiratization_target_views.xml',
        'views/l10n_ae_emiratization_report_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/l10n_ae_hr_payroll_demo.xml'
    ],
    'post_init_hook': '_l10n_ae_hr_payroll_post_install',
    'uninstall_hook': '_l10n_ae_hr_payroll_uninstall_hook',
    'license': 'OEEL-1',
}
