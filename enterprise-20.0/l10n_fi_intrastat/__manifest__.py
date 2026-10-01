{
    'name': 'Finnish Intrastat Declaration',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Generates Intrastat CSV report for declaration based on invoices for Finland.
    """,
    'depends': ['account_intrastat', 'l10n_fi_reports'],
    'data': [
        'data/account_return_data.xml',
        'wizard/intrastat_goods_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
