{  # noqa: B018
    "name": "Phone - Human Resources",
    "summary": "Phone integration with Human Resources module.",
    "category": "Human Resources",
    "depends": ["voip", "hr"],
    "license": "OEEL-1",
    "data": [
        "wizards/mail_activity_schedule_views.xml",
        'security/ir.access.csv',
    ],
    "assets": {
        "im_livechat.assets_embed_core": [
            "voip_hr/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "voip_hr/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "voip_hr/static/src/core/common/**/*",
        ],
        "web.assets_backend": [
            "voip_hr/static/src/**/*",
        ],
    },
    "auto_install": True,
    "author": "Odoo S.A.",
}
