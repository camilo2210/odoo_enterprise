# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale enterprise',
    'category': 'Sales/Point of Sale',
    'summary': 'Advanced features for PoS',
    'description': """
Advanced features for the PoS.
""",
    'data': [
        'views/res_config_settings_views.xml',
        'views/preparation_display_assets_index.xml',
        'views/preparation_display_view.xml',
        'wizard/preparation_display_reset_wizard.xml',
        'data/preparation_display_cron.xml',
        'views/pos_order_view.xml',
        'views/pos_printer_views.xml',
        'views/pos_preparation_time_report_view.xml',
        'security/ir.access.csv',
        'receipt/pos_order_change_receipt.xml',
    ],
    'depends': ['web_enterprise', 'point_of_sale'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_enterprise/static/src/override/point_of_sale/**/*',
            ('remove', 'pos_enterprise/static/src/override/point_of_sale/**/*.dark.scss'),
        ],
        'point_of_sale.assets_pos_dark_styles': [
            ('include', 'web.dark_mode_variables'),
            # web._assets_backend_helpers
            ('before', 'web_enterprise/static/src/scss/bootstrap_overridden.scss', 'web_enterprise/static/src/scss/bootstrap_overridden.dark.scss'),
            ('after', 'web/static/lib/bootstrap/scss/_functions.scss', 'web_enterprise/static/src/scss/bs_functions_overridden.dark.scss'),
            # assets_backend
            'web_enterprise/static/src/**/*.dark.scss',
            'pos_enterprise/static/src/**/*.dark.scss',
        ],
        'point_of_sale.assets_prod_dark': [
            ('include', 'point_of_sale.assets_pos_dark_styles'),
        ],
        'point_of_sale.customer_display_assets_dark': [
            ('include', 'point_of_sale.assets_pos_dark_styles'),
        ],
        'pos_preparation_display.assets_dark': [
            ('include', 'pos_preparation_display.assets'),
            ('include', 'web.dark_mode_variables'),
            'web_enterprise/static/src/**/*.dark.scss',
            'pos_enterprise/static/src/scss/preparation_display_dark.scss',
        ],
        'pos_preparation_display.assets': [
            # 'preparation_display' bootstrap customization layer
            'web/static/src/scss/functions.scss',
            'pos_enterprise/static/src/scss/primary_variables.scss',
            ("include", "point_of_sale.base_app"),
            'web/static/src/webclient/webclient.scss',
            'web/static/src/webclient/icons.scss',
            'point_of_sale/static/src/utils.js',
            "point_of_sale/static/src/app/utils/devices_identifier_sequence.js",
            "point_of_sale/static/src/app/components/popups/retry_print_popup/*",

            'mail/static/src/core/common/sound_effects_plugin.js',
            'point_of_sale/static/src/overrides/sound_effects_plugin.js',
            'pos_enterprise/static/src/app/**/*',
            'web/static/src/core/colorlist/colorlist.scss',

            # receipt related assets
            'point_of_sale/static/src/app/components/epos_templates.xml',
            'point_of_sale/static/src/app/utils/printer/epson_printer.js',
            'point_of_sale/static/src/app/utils/printer/generate_printer_data.js',
            'point_of_sale/static/src/app/components/popups/retry_print_popup/retry_print_popup.js',
            'point_of_sale/static/src/app/utils/html-to-image.js',
            'point_of_sale/static/src/app/components/popups/select_default_printer_popup/select_default_printer_popup.js',
            'point_of_sale/static/src/app/utils/make_awaitable_dialog.js',
            'point_of_sale/static/src/app/utils/printer/base_printer.js',
            'point_of_sale/static/src/app/utils/init_lna.js',
            'point_of_sale/static/src/app/models/utils/order_change.js',
            'point_of_sale/static/src/app/utils/printer/zebra_printer.js',
            'point_of_sale/static/src/app/plugins/pos_ticket_printer_plugin.js',
            # barcode related assets
            'web/static/src/core/debug/**/*',
            'web/static/src/model/**/*',
            'web/static/src/views/**/*',
            'web/static/src/search/**/*',
            'web/static/src/webclient/actions/**/*',
            ('remove', 'web/static/src/webclient/actions/reports/report_layouts.scss'),
            ('remove', 'web/static/src/webclient/actions/**/*css'),
            'barcodes/static/src/barcode_plugin.js',
            'barcodes/static/src/js/barcode_parser.js',
            'web/static/src/webclient/actions/action_plugin.js',
            'barcodes_gs1_nomenclature/static/src/js/barcode_parser.js',
            'point_of_sale/static/src/app/hooks/barcode_reader_hook.js',
            'point_of_sale/static/src/app/services/barcode_reader_service.js',

            # Related models from point_of_sale
            'point_of_sale/static/src/lazy_getter.js',
            'point_of_sale/static/src/app/utils/convert_python_template.js',
            "point_of_sale/static/src/app/models/data_service_options.js",
            "point_of_sale/static/src/app/models/utils/indexed_db.js",
            "point_of_sale/static/src/app/utils/pretty_console_log.js",
            "point_of_sale/static/src/app/models/related_models/**/*",
            "point_of_sale/static/src/app/plugins/pos_data_plugin.js",
            "point_of_sale/static/src/app/models/pos_preset.js",
            "point_of_sale/static/src/app/models/pos_category.js",
            "point_of_sale/static/src/app/utils/debug-formatter.js",
        ],
        'pos_preparation_display.assets_tour_tests': [
            ("include", "point_of_sale.base_tests"),
            "pos_enterprise/static/tests/tours/preparation_display/**/*"
        ],
        'web.assets_tests': [
            'pos_enterprise/static/tests/tours/point_of_sale/**/*',
        ],
        'web.assets_backend': [
            'pos_enterprise/static/src/backend/components/fields/duration_field.js',
            'pos_enterprise/static/src/backend/components/fields/duration_field.xml',
        ],
        'web.assets_unit_tests_setup': [
            ('include', 'pos_preparation_display.assets'),
            ('remove', 'pos_enterprise/static/src/app/root.js'),
            ('remove', 'pos_enterprise/static/src/app/models/pos_order.js'),
            ('remove', 'pos_enterprise/static/src/app/models/product_product.js'),

            # Remove CSS files since we're not testing the UI with hoot in PoS preparation display
            # CSS files make html_editor tests fail
            ('remove', 'pos_enterprise/static/src/**/*.scss'),

            # Re-include debug and router files that were removed in point_of_sale.base_app
            # but are required for running unit tests
            'web/static/src/core/debug/**/*',
            'web/static/src/core/browser/router.js',
        ],
        'web.assets_unit_tests': [
            'pos_enterprise/static/tests/unit/**/*',
        ],
    },
}
