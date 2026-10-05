{
    'name': 'Oman - Payroll Localization',
    'countries': ['om'],
    'category': 'Human Resources/Payroll',
    'summary': 'Setup for Oman payroll localization based on Oman Labor Law.',
    'description': """
Oman Payroll and End of Service rules.
===========================================================
- Monthly Salary Structure
- Social Insurance Computation
- EoS Provisions & Benefits
- Remaining Annual Leave Compensation
- Paid Time Off Types
- Sick Leave Calculation
- Oman Employee Plan
- Overtime Rulesets (Normal & Special)
    """,
    'depends': ['hr_payroll'],
    'auto_install': ['hr_payroll'],
    'data': [
        'data/ir_sequence_data.xml',
        'data/l10n_om_resource_calendar.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_holiday_accrual_plan_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_payroll_warning_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_work_entry_type_data.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_view.xml',
        'wizard/hr_payroll_payment_report_wizard.xml',
    ],
    'demo': [
        'data/l10n_om_hr_payroll_demo.xml',
    ],
    'post_init_hook': '_l10n_om_hr_payroll_post_install',
    'uninstall_hook': '_l10n_om_hr_payroll_uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
