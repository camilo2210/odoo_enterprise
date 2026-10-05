# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Mexican Payroll',
    'category': 'Human Resources/Payroll',
    'summary': 'Attach Mexican payroll CFDI XML to payslips emails',
    'description': """
Integrates the Mexican payroll with the Documents app so that CFDI XML files
can be attached on payslips emails.
""",
    'depends': ['documents_hr_payroll', 'l10n_mx_hr_payroll_account'],
    'data': [
        'data/mail_template_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
