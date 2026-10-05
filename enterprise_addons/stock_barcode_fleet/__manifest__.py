{
    'name': "Stock Barcode Fleet",
    'summary': "Bridge module for stock_barcode and stock_fleet",
    'description': """
Bridge module for stock_barcode and stock_fleet
    """,
    'depends': ['stock_barcode', 'stock_fleet'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'stock_barcode_fleet/static/src/**/*.js',
        ],
    },
}
