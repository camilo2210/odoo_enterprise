{
    "name": "Pricer",
    "category": "Sales/Sales",
    "sequence": 6,
    "summary": "Display and change your products information on electronic Pricer tags",
    "data": [
        "security/ir.access.csv",
        "views/pricer_tag_views.xml",
        "views/pricer_store_views.xml",
        "views/product_views.xml",
        "wizard/product_label_layout_views.xml",
        "data/pricer_ir_cron.xml",
        "data/pricer_data.xml",
    ],
    "demo": [
        "demo/pricer_store.xml",
    ],
    "depends": ["product"],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
