# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Agentic Documents',
    'category': 'Hidden',
    'summary': "Bridge module between AI Agentic and Documents.",
    'depends': ['ai_agentic', 'ai_documents_source'],
    'assets': {
        'web.assets_backend': [
            'ai_agentic_documents/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
