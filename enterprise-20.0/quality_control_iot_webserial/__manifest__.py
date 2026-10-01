{
    "name": "Web Serial devices for Quality Control",
    "category": "Supply Chain/Internet of Things (IoT)",
    "summary": "Control the quality of your products with serial devices",
    "description": """
Use serial devices connected directly with the browser to control the quality of your products.
""",
    "depends": ["quality_control", "iot_webserial"],
    "data": [
        "views/quality_views.xml",
        "wizard/quality_check_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "quality_control_iot_webserial/static/src/**/*",
        ],
    },
    "auto_install": ["quality_control"],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
