{
    "name": "Obox - Android",
    "category": "Hidden",
    "depends": ["obox"],
    "description": "Support of the Obox running in the Odoo Android app.",
    "auto_install": True,
    "data": [
        "views/obox_views.xml",
        "wizards/kiosk_pin_wizard_views.xml",
        "security/ir.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "obox_android/static/src/**/*",
        ],
    },
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
