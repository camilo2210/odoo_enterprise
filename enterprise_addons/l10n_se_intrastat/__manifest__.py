{
    'name': 'Sweden - Intrastat',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Intrastat for Sweden
=====================
    """,
    'depends': ['l10n_se_reports', 'account_intrastat'],
    'data': [
        'data/account_return_data.xml',
        'wizard/intrastat_goods_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
