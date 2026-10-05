{  # noqa: B018
    "name": "Phone - AI",
    "depends": ["voip", "ai"],
    "auto_install": True,
    "category": "Productivity/Phone",
    "summary": "Extend Phone with AI features (such as transcription)",
    "data": [
        "views/voip_call_views.xml",
        "views/voip_provider_views.xml",
        "data/ai_agent_prompts.xml",
        "data/voip_template.xml",
    ],
    "demo": [
        "demo/voip_call.xml",
    ],
    "assets": {
        "im_livechat.assets_embed_core": [
            "voip_ai/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "voip_ai/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "voip_ai/static/src/core/common/**/*",
        ],
        "web.assets_backend": [
            "voip_ai/static/src/**/*",
        ],
    },
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
