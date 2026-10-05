# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'India - Payroll with Accounting',
    'category': 'Human Resources',
    'depends': ['l10n_in_hr_payroll', 'hr_payroll_account', 'l10n_in'],
    'description': """
Accounting Data for Indian Payroll Rules.
==========================================
    """,
    "data": [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    "demo": [
        'data/l10n_in_hr_payroll_account_demo.xml',
    ],
    'auto_install': ['l10n_in_hr_payroll', 'hr_payroll_account'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
