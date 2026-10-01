# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sweden - SIE 4 Export',
    'summary': 'Export Accounting Data to SIE 4 files',
    'description': """
        Module for the export of accounting data to SIE 4 standard files.
        Official website: https://sie.se/
        XSD and documentation: https://sie.se/format/
    """,
    'category': "Accounting/Accounting",
    'depends': [
        'account_base_import',
        'account_reports',
        'l10n_se',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
