# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "AI Text Draft - Knowledge",
    'category': 'Hidden',
    'summary': "AI text draft integration with knowledge",
    'depends': ['ai', 'knowledge'],
    'data': [
        'data/ai_composer_data.xml',
        'wizard/ai_add_knowledge_articles.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_knowledge/static/src/**/*',
        ],
        'web.assets_tests': [
            'ai_knowledge/static/tests/tours/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
