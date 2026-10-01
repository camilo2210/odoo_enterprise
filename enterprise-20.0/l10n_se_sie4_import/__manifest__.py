# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sweden - SIE 4 Import',
    'countries': ['se'],
    'summary': 'Import Accounting Data from SIE 4 files',
    'description': """
        Module for the import of SIE 4 standard files.
        Official website: https://sie.se/
        XSD and documentation: https://sie.se/format/
    """,
    'category': "Accounting/Accounting",
    'depends': [
        'account_base_import',
        'l10n_se',
    ],
    'data': [
        'wizard/import_wizard_view.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_se_sie4_import/static/src/xml/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
