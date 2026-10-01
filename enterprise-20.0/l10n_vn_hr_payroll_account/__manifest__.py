# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Vietnam - Payroll with Accounting',
    'category': 'Human Resources',
    'description': """
Accounting Data for Vietnamese Payroll Rules
============================================
Salary journal and default accounts of the Vietnamese chart of accounts (Circular 200/2014/TT-BTC):
staff costs (6421), employees payable (334), social, health and unemployment insurance (3383, 3384, 3386),
trade union fees (3382), personal income tax (3335), advances (141) and other payables (3388).
    """,
    'depends': ['hr_payroll_account', 'l10n_vn', 'l10n_vn_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
        'data/hr_salary_rule_data.xml',
    ],
    'demo': [
        'data/l10n_vn_hr_payroll_account_demo.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': ['l10n_vn_hr_payroll', 'hr_payroll_account'],
}
