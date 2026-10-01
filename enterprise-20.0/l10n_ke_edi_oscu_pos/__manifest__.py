{
    'name': 'Kenya - Point of Sale',
    'countries': ['ke'],
    'category': 'Accounting/Localizations/EDI',
    'depends': [
        'l10n_ke_edi_oscu_stock',
        'pos_stock',
    ],
    'data': [
        'views/account_move_views.xml',
        'views/pos_order.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'receipt/pos_order_receipt.xml',
    ],
    'demo': [
        'demo/demo_product.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n_ke_edi_oscu_pos/static/src/app/**/*',
            'l10n_ke_edi_oscu_pos/static/src/components/**/*',
            'l10n_ke_edi_oscu_pos/static/src/overrides/components/**/*',
            'l10n_ke_edi_oscu_pos/static/src/overrides/models/*.js',
        ],
        'web.assets_backend': [
            'l10n_ke_edi_oscu_pos/static/src/overrides/views/*.js',
            'l10n_ke_edi_oscu_pos/static/src/overrides/views/*.xml',
        ],
        'web.assets_tests': [
            'l10n_ke_edi_oscu_pos/static/tests/**/*',
        ],
    },
    'post_init_hook': 'set_update_stock_real_time',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
