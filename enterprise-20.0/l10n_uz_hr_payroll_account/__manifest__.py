# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Uzbekistan - Payroll with Accounting',
    'author': 'Odoo S.A.',
    'category': 'Human Resources',
    'description': """
Accounting Data for Uzbekistan Payroll Rules
============================================
    """,
    'depends': ['hr_payroll_account', 'l10n_uz', 'l10n_uz_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'demo': [
        'data/l10n_uz_hr_payroll_account_demo.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': ['l10n_uz_hr_payroll', 'hr_payroll_account'],
}
