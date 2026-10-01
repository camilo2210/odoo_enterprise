{
    "name": "Phone - Project",
    "summary": "Phone integration with Project module.",
    "category": "Services/Project",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": ["voip", "project"],
    "auto_install": True,
    "data": [
        "views/voip_call_views.xml",
        "wizards/mail_activity_schedule_views.xml",
    ],
    "demo": [
        "demo/voip_call.xml",
    ],
    "assets": {
        "im_livechat.assets_embed_core": [
            "voip_project/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "voip_project/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "voip_project/static/src/core/common/**/*",
        ],
        "web.assets_backend": [
            "voip_project/static/src/**/*",
        ],
    },
}
