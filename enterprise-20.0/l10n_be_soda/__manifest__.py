# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Belgium - Import SODA files',
    'category': 'Accounting/Localizations',
    'description': '''
Module to import SODA files.
======================================
''',
    'depends': ['accountant', 'l10n_be'],
    'data': [
        'views/account_journal_dashboard_view.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/soda_import_wizard.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
