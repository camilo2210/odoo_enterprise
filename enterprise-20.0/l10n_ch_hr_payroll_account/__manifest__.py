# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Switzerland - Payroll with Accounting',
    'icon': '/account/static/description/l10n.png',
    'author': 'Odoo S.A.',
    'category': 'Human Resources',
    'description': """
Accounting Data for Switzerland Payroll Rules
=============================================
    """,
    'depends': ['hr_payroll_account', 'l10n_ch', 'l10n_ch_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_salary_rule_views.xml',
    ],
    'demo': [
        'data/l10n_ch_hr_payroll_account_demo.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': ['l10n_ch_hr_payroll', 'hr_payroll_account'],
}
