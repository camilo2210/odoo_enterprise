{
    "name": "Latvia - Tax Report",
    'category': 'Accounting/Localizations/Reporting',
    "description": """
Tax Report
- Including attachments
- XML Export
""",
    "depends": ['l10n_lv_reports'],
    'data': [
        'data/vat_tax_report_attachment_1i.xml',
        'data/vat_tax_report_attachment_1ii.xml',
        'data/vat_tax_report_attachment_1iii.xml',
        'data/vat_tax_report_attachment_2.xml',
        'data/vat_tax_report.xml',
        'data/account_return_data.xml',
        'wizard/vat_report_export.xml',
        'views/vat_report_export_templates.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_lv_reports'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
