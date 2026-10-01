# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI',
    'category': 'Hidden',
    'summary': "A powerful suite of AI tools and agents integrated directly into your Odoo environment",
    'description': """
        * Create and manage AI agents for various business tasks
        * Integrate with popular AI models and services
        * Process documents and extract information automatically
        * Enhance customer service with AI-powered responses
        * Automate routine tasks with intelligent workflows
    """,
    'depends': ['attachment_indexation', 'ai', 'base_automation'],
    'data': [
        'security/ir.access.csv',
        'data/ir_actions_server_data.xml',
        'data/ai_skill_data.xml',
        'data/ai_agent_data.xml',
        'views/base_automation_views.xml',
        'views/ir_actions_server_views.xml',
        'views/ai_agent_views.xml',
        'views/ai_skill_views.xml',
        'views/ai_composer_views.xml',
        'views/ai_menus.xml',
        'views/ai_prompt_button_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_agentic/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'ai_agentic/static/tests/**/*',
        ],
        'mail.assets_public': [
            'ai_agentic/static/src/discuss/core/common/**/*',
        ],
        'im_livechat.assets_embed_core': [
            'ai_agentic/static/src/discuss/core/common/**/*',
        ],
        'portal.assets_chatter_helpers': [
            'ai_agentic/static/src/discuss/core/common/**/*',
        ],
    },
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'iap_paid_service': True,
}
