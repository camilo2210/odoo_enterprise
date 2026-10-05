# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI HTML Builder',
    'category': 'AI',
    'summary': "AI HTML Builder",
    'depends': ['ai', 'html_builder'],
    'assets': {
        'html_builder.assets': [
            'ai_html_builder/static/src/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
