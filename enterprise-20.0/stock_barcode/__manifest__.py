
{
    'name': "Barcode",
    'summary': "Use barcode scanners to process logistics operations",
    'description': """
This module enables the barcode scanning feature for the warehouse management system.
    """,
    'category': 'Supply Chain/Inventory',
    'sequence': 255,
    'depends': ['stock', 'web_tour', 'web_mobile'],
    'data': [
        'security/stock_barcode_security.xml',
        'views/stock_inventory_views.xml',
        'views/stock_package_type_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_picking_batch_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_move_views.xml',
        'views/stock_barcode_views.xml',
        'views/res_config_settings_views.xml',
        'views/stock_location_views.xml',
        'views/stock_lot_views.xml',
        'views/stock_quant_views.xml',
        'wizard/stock_barcode_cancel_operation.xml',
        'wizard/stock_backorder_confirmation_views.xml',
        'data/data.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'auto_install': True,
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'stock_barcode/static/src/**/*.js',
            'stock_barcode/static/src/**/*.scss',
            'stock_barcode/static/src/**/*.xml',

            # Don't include dark mode files in light mode
            ('remove', 'stock_barcode/static/src/**/*.dark.scss'),
        ],
        "web.assets_web_dark": [
            'stock_barcode/static/src/**/*.dark.scss',
        ],
        'web.assets_unit_tests': [
            'stock_barcode/static/tests/units/*.test.js',
        ],
        'web.assets_tests': [
            'stock_barcode/static/tests/tours/**/*',
        ],
    },
    'other_files': [
        'data/epc_template.xml',
    ],
}
