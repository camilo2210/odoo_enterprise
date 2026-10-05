{
    "name": "eCommerce Rental with Stock Management",
    "category": "Website/Website",
    "summary": "Sell rental products on your eCommerce and manage stock",
    "description": """
This module allows you to sell rental products in your eCommerce with
appropriate views and selling choices.
    """,
    "depends": ["website_sale_renting", "website_sale_stock", "sale_stock_renting"],
    "assets": {
        "web.assets_frontend": [
            "website_sale_stock_renting/static/src/interactions/**/*",
            "website_sale_stock_renting/static/src/js/**/*",
            "website_sale_stock_renting/static/src/xml/*.xml",
        ],
        "web.assets_tests": ["website_sale_stock_renting/static/tests/tours/**/*"],
    },
    "auto_install": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
