{
    'name': 'Hungary - A60 accounting Reports',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
A60 accounting reports for Hungary
    """,
    'depends': [
        'l10n_hu_reports',
    ],
    'data': [
        'data/A60/l10n_hu_A60_export_file.xml',
        'data/A60/l10n_hu_A60_report_page_1.xml',
        'data/A60/l10n_hu_A60_report_page_2.xml',
        'data/A60/l10n_hu_A60_report_page_3.xml',
        'data/A60/l10n_hu_A60_report_page_4.xml',
        'data/A60/l10n_hu_A60_report.xml',
        'data/account_return_data.xml',
        'wizard/a60_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
