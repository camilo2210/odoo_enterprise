# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Philippines Payroll',
    'category': 'Human Resources/Payroll',
    'summary': 'Store payroll declarations in the Document app',
    'description': """
Employee declarations will be automatically integrated to the Document app.
""",
    'depends': ['documents_hr_payroll', 'l10n_ph_hr_payroll'],
    'data': [
        'views/l10n_ph_hr_payroll_2316_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
