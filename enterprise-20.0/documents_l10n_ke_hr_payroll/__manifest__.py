# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Kenyan Payroll',
    'category': 'Human Resources/Payroll',
    'summary': 'Store employee tax deduction card forms in the Document app',
    'description': """
Employee Tax Deduction Card forms will be automatically integrated to the Document app.
""",
    'depends': ['documents_hr_payroll', 'l10n_ke_hr_payroll'],
    'data': [
        'views/l10n_ke_tax_deduction_card_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
