{
    "name": "Obox - Odoo IoT management",
    "category": "Administration/IoT",
    "depends": ["bus", "web", "printer"],
    "description": """
This module provides management of your Odoo IoT Boxes (Obox) inside Odoo.
Obox are Odoo IoT Boxes, hardware devices that can be used to connect external
devices (like printers, scales, payment terminals, etc.) to Odoo.

This module allows you to manage your Obox devices, their certificates,
and their connections to your Odoo databases.
    """,
    "application": True,
    "demo": [
        "demo/obox_demo.xml",
    ],
    "data": [
        "security/obox_groups.xml",
        "views/obox_views.xml",
        'views/obox_device_views.xml',
        "views/obox_queue_views.xml",
        "views/obox_menu_views.xml",
        "views/printer_views.xml",
        "wizards/offline_connect_wizard.xml",
        'security/ir.access.csv',
    ],
    "assets": {
        "web.assets_backend": [
            "obox/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "obox/static/tests/**/*.test.js",
        ],
    },
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
