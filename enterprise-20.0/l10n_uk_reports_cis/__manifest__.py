{
    'name': 'UK - Construction Industry Scheme',
    'author': 'Odoo S.A.',
    'category': 'Accounting/Localizations/UK/CIS',
    'description': """
Construction Industry Scheme for United Kingdom
================================================
    """,
    'depends': [
        'l10n_uk_reports',
        'l10n_uk_hmrc',
    ],
    'data': [
        'data/cis_report.xml',
        'data/account_return_data.xml',
        'data/ir_cron.xml',
        'data/mail_template_data.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'wizard/monthly_return_wizard.xml',
        'security/ir.access.csv',
        'views/account_return_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_uk_reports_cis/static/src/components/**/*',
        ],
    },
    'license': 'OEEL-1',
    'other_files': [
        'templates/hmrc_transaction_body_cis.xml',
    ],
}
