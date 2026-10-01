# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Social AI",
    "category": "Marketing/Social Marketing",
    "sequence": 190,
    "summary": "Write social post using AI.",
    "description": "Write social post using AI.",
    "website": "https://www.odoo.com/app/social-marketing",
    "depends": ["ai", "ai_livechat", "social"],
    "data": [
        "data/ir_actions_server_data.xml",
        "data/ai_skill_data.xml",
        "data/ai_agent_data.xml",
        "data/ai_composer_data.xml",
        "views/im_livechat_channel_views.xml",
    ],
    "auto_install": True,
    "assets": {
        "web.assets_backend": [
            "ai_social/static/src/social_post_message_field/*",
        ],
    },
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
