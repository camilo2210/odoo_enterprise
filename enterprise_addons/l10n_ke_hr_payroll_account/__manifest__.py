# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Kenya - Payroll with Accounting',
    'author': 'Odoo S.A.',
    'category': 'Human Resources',
    'description': """
Accounting Data for Kenyan Payroll Rules
========================================
    """,
    'depends': ['hr_payroll_account', 'l10n_ke', 'l10n_ke_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': ['l10n_ke_hr_payroll', 'hr_payroll_account'],
}
