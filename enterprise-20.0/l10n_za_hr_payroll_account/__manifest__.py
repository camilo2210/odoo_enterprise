# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'South Africa - Payroll with Accounting',
    'author': 'Odoo S.A.',
    'category': 'Human Resources',
    'description': """
Accounting Data for South African Payroll Rules
================================================
    """,
    'depends': ['hr_payroll_account', 'l10n_za', 'l10n_za_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': ['l10n_za_hr_payroll', 'hr_payroll_account'],
}
