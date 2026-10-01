{
    'name': "Guatemalan Accounting EDI for POS",
    'countries': ['gt'],
    'category': 'Accounting/Localizations/EDI',
    'icon': '/account/static/description/l10n.png',
    'description': """
Extends the Point of Sale module to comply with Guatemalan electronic invoicing regulations (FEL).
    """,
    'depends': ['l10n_gt_edi', 'point_of_sale'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n_gt_edi_pos/static/src/**/*',
        ],
        'web.assets_tests': [
            'l10n_gt_edi_pos/static/tests/tours/**/*',
        ],
    },
    'auto_install': True,
    'author': "Odoo S.A.",
    'license': 'OEEL-1',
}
