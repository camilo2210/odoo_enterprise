{
    'name': "Türkiye - e-Irsaliye Receipt Response",
    'countries': ['tr'],
    'category': 'Accounting/Localizations',
    'summary': "Answer a received e-Dispatch with a Unit Count quality check",
    'description': """
Records what was received, accepted and rejected per product on a Unit Count quality check, and sends the answer to GİB through Nilvera.
    """,
    'depends': ['l10n_tr_nilvera_edispatch', 'quality_control'],
    'data': [
        'security/ir.access.csv',
        'data/quality_data.xml',
        'data/ir_cron_data.xml',
        'views/quality_views.xml',
        'views/stock_picking_views.xml',
        'wizard/quality_check_wizard_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
