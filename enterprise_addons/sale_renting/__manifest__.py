{
    "name": "Rental",
    "summary": "Manage rental contracts, deliveries and returns",
    "description": """
Specify rentals of products (products, quotations, invoices, ...)
Manage status of products, rentals, delays
Manage user and manager notifications
    """,
    "website": "https://www.odoo.com/app/rental",
    "category": "Sales/Sales",
    "sequence": 160,
    "depends": ["sale", "web_gantt"],
    "data": [
        "data/rental_tour.xml",
        "views/product_pricelist_item_views.xml",
        "views/product_product_views.xml",
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
        "views/sale_order_line_views.xml",
        "views/sale_portal_templates.xml",
        "views/res_config_settings_views.xml",
        "report/rental_order_report_templates.xml",
        "report/rental_report_views.xml",
        "wizard/rental_processing_views.xml",
        "views/sale_renting_menus.xml",
        'security/ir.access.csv',
    ],
    "demo": ["data/rental_demo.xml"],
    "application": True,
    "assets": {
        "web.assets_backend": [
            "sale_renting/static/src/js/**/*",
            ("remove", "sale_renting/static/src/js/**/*.dark.scss"),
            "sale_renting/static/src/scss/sale_order_views.scss",
        ],
        "web.assets_web_dark": [
            "sale_renting/static/src/scss/**/*.dark.scss",
            "sale_renting/static/src/js/**/*.dark.scss",
        ],
        "web.assets_backend_lazy": [
            "sale_renting/static/src/views/schedule_gantt/**",
            "sale_renting/static/src/views/dashboard_list_view/**",
            "sale_renting/static/src/views/dashboard_kanban_view/**",
        ],
        "web.assets_tests": ["sale_renting/static/tests/tours/*"],
    },
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
