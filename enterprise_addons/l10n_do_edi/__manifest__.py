{
    'name': 'Dominican Republic - Accounting EDI',
    'countries': ['do'],
    'category': 'Accounting/Localizations/EDI',
    'description': """Accounting EDI for Dominican Republic""",
    'author': 'Odoo S.A.',
    'depends': [
        'l10n_do',
    ],
    'data': [
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/account_tax_views.xml',
        'views/l10n_latam_document_type_views.xml',
        'views/l10n_do_edi_document_type_range_views.xml',
        'views/report_invoice.xml',
        'wizards/account_move_reversal_views.xml',
        'wizards/account_debit_note_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/demo_l10n_do_edi_document_type_range.xml',
        'demo/demo_l10n_latam_document_type.xml',
    ],
    'license': 'OEEL-1',
}
