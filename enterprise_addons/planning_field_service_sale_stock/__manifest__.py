# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Stock',
    'category': 'Human Resources/Planning',
    'summary': 'Validate stock moves for product added on sales orders through an intervention planned',
    'description': """
Validate stock moves for Field Service
======================================
""",
    'depends': ['planning_field_service_sale_timesheet', 'planning_field_service_stock', 'sale_stock'],
    'data': [
        'views/planning_slot_views.xml',
        'views/stock_move_views.xml',
        'wizard/field_service_stock_tracking_views.xml',
        'views/product_product_views.xml',
        'security/ir.access.csv',
        'views/planning_vehicle_warehouse_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'planning_field_service_sale_stock/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'planning_field_service_sale_stock/static/tests/product_catalog.test.js',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
