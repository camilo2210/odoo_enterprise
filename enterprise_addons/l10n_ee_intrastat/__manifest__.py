{
    'name': 'Estonia Intrastat Declaration',
    'category': 'Accounting/Localizations/Reporting',
    'description': "Generates Intrastat XML report for declaration.",
    'depends': ['l10n_ee_reports', 'account_intrastat'],
    'data': [
        'data/account_return_data.xml',
        'data/intrastat_export.xml',
        'wizard/intrastat_goods_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
