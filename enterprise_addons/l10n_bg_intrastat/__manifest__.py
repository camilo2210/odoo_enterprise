{
    'name': "Bulgarian Intrastat Declaration",
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Bulgaria - Intrastat Report
    """,
    'depends': ['account_intrastat', 'l10n_bg'],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
