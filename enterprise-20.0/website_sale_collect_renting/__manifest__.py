# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "eCommerce Rental with Click and Collect",
    "category": "Website/Website",
    "summary": "Click and Collect for rental products on the eCommerce website.",
    "description": "Allows customers to check in-store stock for rental products",
    "depends": ["website_sale_stock_renting", "website_sale_collect"],
    "data": [
        "views/delivery_form_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_sale_collect_renting/static/src/**/*"
        ],
    },
    "auto_install": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
