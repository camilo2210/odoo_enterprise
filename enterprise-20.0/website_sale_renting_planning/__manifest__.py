{
    "name": "eCommerce Rental with Planning",
    "category": "Website/Website",
    "summary": "Sell rental products on your eCommerce and plan your material resources",
    "description": """
This module allows you to sell rental products in your eCommerce with
appropriate views and selling choices.
    """,
    "depends": ["website_sale_renting", "sale_renting_planning"],
    "assets": {
        "web.assets_frontend": ["website_sale_renting_planning/static/src/interactions/**/*"],
        "web.assets_tests": ["website_sale_renting_planning/static/tests/tours/**/*"],
    },
    "auto_install": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
