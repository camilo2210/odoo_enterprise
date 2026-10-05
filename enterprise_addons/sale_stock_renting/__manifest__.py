{
    'name': "Rental Stock Management",
    'summary': "Allows use of stock application to manage rentals inventory",
    'description': """

    """,
    'category': 'Sales/Sales',
    'depends': ['sale_renting', 'sale_stock'],
    'data': [
        'security/sale_stock_renting_security.xml',
        'security/ir.access.csv',
        'data/rental_stock_data.xml',
        'wizard/rental_processing_views.xml',
        'report/rental_report_views.xml',
        'report/rental_order_report_templates.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_line_views.xml',
        'views/product_template_views.xml',
        'views/res_company_views.xml',
        'views/stock_lot_views.xml',
    ],
    'demo': ['data/rental_stock_demo.xml'],
    'auto_install': True,
    'post_init_hook': '_ensure_rental_stock_moves_consistency',
    'assets': {
        'web.assets_backend': ['sale_stock_renting/static/src/widgets/**/*'],
        'web.assets_backend_lazy': ['sale_stock_renting/static/src/views/**/*'],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
