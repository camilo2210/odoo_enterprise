{
    'name': "Austrian Intrastat Declaration",
    'category': "Accounting/Localizations/Reporting",
    'description': """
Generates Intrastat PDF report for declaration based on invoices.
        """,
    'depends': ['account_intrastat', 'l10n_at_reports'],
    'data': [
        'data/account_return_data.xml',
    ],
    'author': "Odoo S.A.",
    'license': 'OEEL-1',
    'auto_install': True,
}
