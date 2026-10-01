{
    'name': 'Belgian Standard Audit File for Tax',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Belgian SAF-T is a standard file format for exporting various types of accounting transactional data using the XML format.
The SAF-T Financial is limited to the general ledger level including customer and supplier transactions.
Necessary master data is also included.
    """,
    'depends': [
        'l10n_be', 'account_saft'
    ],
    'data': [
        'data/saft_report.xml',
    ],
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
