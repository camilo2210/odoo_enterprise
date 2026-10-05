# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents - Hong Kong Payroll',
    'category': 'Human Resources/Payroll',
    'summary': 'Store ir56 forms in the Document app',
    'description': """
Employee ir56 forms will be automatically integrated to the Document app.
""",
    'depends': ['documents_hr_payroll', 'l10n_hk_hr_payroll'],
    'data': [
        'views/l10n_hk_ir56b_views.xml',
        'views/l10n_hk_ir56e_views.xml',
        'views/l10n_hk_ir56f_views.xml',
        'views/l10n_hk_ir56g_views.xml',
        'views/l10n_hk_ir56m_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
