# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'United States - Payroll with Accounting',
    'author': 'Odoo S.A.',
    'category': 'Human Resources',
    'description': """
Accounting Data for United States Payroll Rules
===============================================
    """,
    'depends': ['hr_payroll_account', 'l10n_us_hr_payroll', 'l10n_us_payment_nacha'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_payslip_run_views.xml',
        'wizard/hr_payroll_payment_report_wizard.xml',
    ],
    'demo': [
        'data/l10n_us_hr_payroll_account_demo.xml',
    ],
    'license': 'OEEL-1',
    'uninstall_hook': '_l10n_us_hr_payroll_uninstall_hook',
    'auto_install': ['l10n_us_hr_payroll', 'hr_payroll_account'],
}
