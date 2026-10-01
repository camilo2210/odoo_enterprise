{
    'name': 'German Intrastat Declaration',
    'icon': '/account/static/description/l10n.png',
    'category': 'Accounting/Localizations/Reporting',
    'description': "Generates Intrastat XML report for declaration.",
    'depends': ['l10n_de', 'account_intrastat'],
    'data': [
        'data/code_region_data.xml',
        'data/intrastat_export.xml',
        'views/res_company_settings_view.xml',
        'data/account_return_data.xml',
    ],
    'auto_install': ['l10n_de', 'account_intrastat'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
