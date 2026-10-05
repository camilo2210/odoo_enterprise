# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Website Blog Livechat',
    'category': 'AI',
    'summary': "AI Website Blog preview cards for website livechat",
    'depends': ['ai_website_livechat', 'website_blog'],
    'assets': {
        'web.assets_frontend': [
            'ai_website_blog_livechat/static/src/scss/ai_blog_preview.scss',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
