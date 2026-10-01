# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Barcode Expiry - Barcode Lookup",
    'category': 'Inventory/Inventory',
    'depends': ['stock_barcode_barcodelookup', 'product_expiry'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'views/product_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_barcode_barcodelookup_product_expiry/static/src/**/*',
        ],
    },
}
