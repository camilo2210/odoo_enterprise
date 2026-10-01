{
    "name": "Phone - Sales",
    "summary": "Phone integration with Sales module.",
    "category": "Services/Sales",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": ["voip", "sale"],
    "auto_install": True,
    "data": [
        "views/voip_call_views.xml",
        "wizards/mail_activity_schedule_views.xml",
    ],
    "assets": {
        "im_livechat.assets_embed_core": [
            "voip_sale/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "voip_sale/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "voip_sale/static/src/core/common/**/*",
        ],
        "web.assets_backend": [
            "voip_sale/static/src/**/*",
        ],
    },
}
