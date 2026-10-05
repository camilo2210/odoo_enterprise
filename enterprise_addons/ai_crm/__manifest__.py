# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "AI crm",
    "summary": "Automatically create leads.",
    "description": "Automatically create leads.",
    "author": "Odoo S.A.",
    "category": "Hidden",
    "license": "OEEL-1",
    "depends": ["ai", "crm"],
    "auto_install": True,
    "data": [
        "data/ir_actions_server_tools.xml",
        "data/ai_skill.xml",
    ],
}
