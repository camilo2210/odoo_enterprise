{
    'name': "Hungarian Intrastat Declaration",
    'category': 'Accounting/Localizations/Reporting',
    'description': """
        Hungary - Intrastat report
    """,
    'depends': ['account_intrastat', 'l10n_hu_reports'],
    'data': [
        'data/account_return_data.xml',

        'views/res_company_views.xml',

        'wizard/intrastat_goods_submission_wizard.xml',
        'wizard/intrastat_goods_contact_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
