{
    'name': "Portuguese Intrastat Declaration",
    'category': "Accounting/Localizations/Reporting",
    'description': """
Generates Intrastat PDF report for declaration based on invoices.
        """,
    'depends': ['l10n_pt', 'account_intrastat'],
    'data': [
        'data/account_return_data.xml',
    ],
    'auto_install': True,
    'author': "Odoo S.A.",
    'license': 'OEEL-1',
}
