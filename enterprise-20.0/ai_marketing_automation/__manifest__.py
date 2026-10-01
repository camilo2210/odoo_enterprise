# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "AI Marketing Automation",
    "summary": "Automatically create campaigns from livechat.",
    "description": "Automatically create campaigns from livechat.",
    "author": "Odoo S.A.",
    "category": "Hidden",
    "license": "OEEL-1",
    "depends": ["marketing_automation", "ai"],
    "auto_install": True,
    "data": [
        "data/ir_actions_server_data.xml",
        "data/ai_skill.xml",
        "data/ai_agent.xml",
        "data/ai_composer_data.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'ai_marketing_automation/static/src/components/**/*',
        ]
    }
}
