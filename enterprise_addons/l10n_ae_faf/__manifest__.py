{
    'name': 'United Arab Emirates - FTA VAT Audit',
    'description': """
        Accounting reports:
        - FTA VAT Audit
    """,
    'depends': ['l10n_ae_reports'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/account_move_views.xml',
        'views/account_tax_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_ae_faf/static/src/components/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
