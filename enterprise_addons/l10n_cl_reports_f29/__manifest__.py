{
    'name': 'Chile - Accounting Reports - F29',
    'author': 'Odoo S.A.',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
F29 Accounting reports for Chile
    """,
    'depends': ['l10n_cl_reports'],
    'data': [
        'data/tax_report_f29.xml',
        'data/account_return_data.xml',
        'wizard/f29_submission_wizard_views.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
