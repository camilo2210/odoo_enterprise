# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "AI Documents Source",
    "category": "Hidden",
    "summary": "Add documents to AI agents as sources.",
    "description": "Add documents to AI agents as sources.",
    "depends": ["ai", "documents"],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "auto_install": True,
    "assets": {
        "web.assets_backend": [
            "ai_documents_source/static/src/**/*",
        ],
        'web.assets_unit_tests': [
            'ai_documents_source/static/tests/**/*',
        ],
    },
}
