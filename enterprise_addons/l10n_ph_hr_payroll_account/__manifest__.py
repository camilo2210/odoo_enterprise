# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Philippines - Payroll with Accounting',
    'author': 'Odoo S.A.',
    'category': 'Human Resources',
    'description': """
Accounting Data for Philippines Payroll Rules
=============================================
    """,
    'depends': ['hr_payroll_account', 'l10n_ph', 'l10n_ph_hr_payroll'],
    'data': [
        'data/account_chart_template_data.xml',
    ],
    'demo': [
        'demo/res_company_demo.xml',
    ],
    'license': 'OEEL-1',
    'auto_install': ['l10n_ph_hr_payroll', 'hr_payroll_account'],
}
