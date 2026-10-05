{
    'name': 'Codaclean',
    'author': 'Odoo S.A.',
    'website': 'https://www.odoo.com/documentation/latest/applications/finance/fiscal_localizations/belgium.html#codaclean',
    'category': 'Accounting/Localizations',
    'description': 'Connect to Codaclean and automatically import CODA statements.',
    'depends': [
        'l10n_be_coda',
        'l10n_be_soda',
    ],
    'data': [
        'data/ir_cron.xml',
        'views/account_journal_dashboard_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/connection_wizard.xml',
        'security/ir.access.csv',
    ],
    'license': 'OEEL-1',
}
