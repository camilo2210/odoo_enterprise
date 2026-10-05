{
    'name': 'Malta Intrastat Declaration',
    'category': 'Accounting/Localizations/Reporting',
    'description': 'Intrastat for Malta',
    'depends': ['l10n_mt_reports', 'account_intrastat'],
    'data': [
        'data/account_return_data.xml',
        'wizard/intrastat_goods_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
