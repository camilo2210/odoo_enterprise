# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "TikTok Shop Connector",
    "summary": "Import TikTok Shop orders and sync deliveries",
    "description": """
Import your TikTok Shop orders in Odoo and synchronize deliveries
=================================================================

Key Features
------------
* Import orders from multiple shops
* Orders are matched with Odoo products based on their internal reference
  (SKU in TikTok Shop)
* Support for Fulfillment by Seller (FBS)
""",
    "category": "Sales/Sales",
    "sequence": 325,
    "application": True,
    "depends": ["sale_management", "stock_delivery"],
    "data": [
        "data/mail_template_data.xml",
        "data/ir_cron.xml",
        "data/data.xml",
        "security/ir.access.csv",
        "wizard/tiktok_shop_create_wizard_views.xml",
        "wizard/tiktok_picking_ship_wizard_views.xml",
        "views/sale_order_views.xml",
        "views/tiktok_shop_views.xml",
        "views/tiktok_item_views.xml",
        "views/stock_picking_views.xml",
        "views/menus.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
