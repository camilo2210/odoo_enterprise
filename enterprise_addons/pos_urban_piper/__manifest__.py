# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale - UrbanPiper',
    'category': 'Sales/Point of Sale',
    'description': """
This module integrates with UrbanPiper to receive and manage orders from various food delivery platforms.
    """,
    'depends': ['pos_enterprise', 'pos_discount'],
    'data': [
        'security/security.xml',
        'data/pos_delivery_provider_data.xml',
        'data/product_product_data.xml',
        'data/ir_cron.xml',
        'data/preset_data.xml',
        'views/pos_urbanpiper_store_views.xml',
        'views/urbanpiper_store_aggragator_views.xml',
        'views/res_config_settings_views.xml',
        'views/pos_category_views.xml',
        'views/pos_order_views.xml',
        'views/product_attribute_views.xml',
        'views/product_views.xml',
        'views/pos_payment_method_views.xml',
        'views/pos_preset_views.xml',
        'views/pos_order_report_view.xml',
        'views/report_invoice.xml',
        'wizard/pos_urban_piper_test_order.xml',
        'receipt/pos_order_receipt.xml',
        'receipt/pos_order_change_receipt.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/urbanpiper_store_data.xml',
    ],
    'post_init_hook': 'urbanpiper_post_init',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_urban_piper/static/src/point_of_sale_override/**/*',
            'pos_urban_piper/static/src/utils.js',
        ],
        'pos_preparation_display.assets': [
            'pos_urban_piper/static/src/pos_preparation_display_override/**/*',
            'pos_urban_piper/static/src/utils.js',
            'pos_urban_piper/static/src/point_of_sale_override/utils/printer/generate_printer_data.js',
        ],
        'web.assets_tests': [
            'pos_urban_piper/static/tests/tours/point_of_sale/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_urban_piper/static/tests/unit/**/*'
        ],
        'pos_preparation_display.assets_tour_tests': [
            'pos_urban_piper/static/tests/tours/preparation_display/**/*',
        ],
        'web.assets_unit_tests_setup': [
            ('remove', 'pos_urban_piper/static/src/pos_preparation_display_override/models/pos_order.js'),
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
