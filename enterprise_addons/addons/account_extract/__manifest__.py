{
    'name': 'Account Extract',
    'category': 'Accounting/Accounting',
    'summary': 'Digitise and extract data from documents.',
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'depends': ['account', 'iap_extract', 'iap_mail', 'mail_enterprise', 'account_bank_statement_import'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
