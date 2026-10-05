{
    'name': 'Norway SAF-T Import',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Norwegian SAF-T is standard file format for exporting various types of accounting transactional data using the XML format.
This module allow to import data.
    """,
    'depends': [
        'l10n_no', 'account_saft_import',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'auto_install': True,
}
