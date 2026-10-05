# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Romania - Payroll with Accounting',
    'category': 'Human Resources/Payroll',
    'description': """
Accounting Data for Romania Payroll Rules
=========================================
    """,
    'depends': ['hr_payroll_account', 'l10n_ro', 'l10n_ro_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'demo': [
        'data/l10n_ro_hr_payroll_account_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': ['l10n_ro_hr_payroll', 'hr_payroll_account'],
}
