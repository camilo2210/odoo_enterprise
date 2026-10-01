{
    'name': 'Romania - EC Sales List D390 Report',
    'author': 'Odoo S.A.',
    'category': 'Accounting/Localizations/Reporting',
    'depends': ['l10n_ro_reports_d300'],
    'description': """
This module supports the generation of Declarația 390 Report for Romanian EC Sales List.
    """,
    'data': [
        'data/account_report_data.xml',
        'data/account_report_ro_ec_sales_d390_report.xml',
        'data/account_return_data.xml',
        'wizard/ec_sales_list_submission_wizard.xml',
        'wizard/generate_ec_sales_report_wizard.xml',
        'security/ir.access.csv',
    ],
    'license': 'OEEL-1',
}
