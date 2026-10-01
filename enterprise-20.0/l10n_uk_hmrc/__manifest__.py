{
    'name': 'UK - HMRC API',
    'countries': ['gb'],
    'author': 'Odoo S.A.',
    'category': 'Accounting/Localizations/UK/HMRC',
    'description': """
HMRC API for the United Kingdom
================================================
    """,
    'depends': [
        'l10n_uk',
    ],
    'data': [
        'data/config_parameter.xml',
        'data/ir_cron.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'security/ir.access.csv',
    ],
    'license': 'OEEL-1',
    'other_files': [
        'templates/hmrc_transaction_base.xml',
        'templates/hmrc_transaction_request.xml',
    ],
}
