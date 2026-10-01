# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Belgian Payroll',
    'category': 'Human Resources/Payroll',
    'summary': 'Store employee 281.10 and 281.45 forms in the Document app',
    'description': """
Employee 281.10 and 281.45 forms will be automatically integrated to the Document app.
""",
    'depends': ['documents_hr_payroll', 'l10n_be_hr_payroll'],
    'data': [
        'views/l10n_be_individual_account_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
