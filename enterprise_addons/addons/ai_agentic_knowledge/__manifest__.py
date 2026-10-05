# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Agentic Knowledge',
    'category': 'Hidden',
    'summary': "Bridge module between AI Agentic and Knowledge.",
    'depends': ['ai_agentic', 'ai_knowledge'],
    'assets': {
        'web.assets_backend': [
            'ai_agentic_knowledge/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
