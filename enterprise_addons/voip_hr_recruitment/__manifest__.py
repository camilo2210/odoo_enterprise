{  # noqa: B018
    "name": "Phone - Recruitement",
    "summary": "Phone integration with Recruitment module.",
    "category": "Human Resources/Recruitment",
    "depends": ["hr_recruitment", "voip"],
    "auto_install": True,
    "license": "OEEL-1",
    "data": [
        "views/voip_call_views.xml",
    ],
    "assets": {
        "im_livechat.assets_embed_core": [
            "voip_hr_recruitment/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "voip_hr_recruitment/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "voip_hr_recruitment/static/src/core/common/**/*",
        ],
        "web.assets_backend": [
            "voip_hr_recruitment/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "voip_hr_recruitment/static/tests/**/*",
        ],
    },
    "author": "Odoo S.A.",
}
