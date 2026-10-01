# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Website Sale Livechat',
    'category': 'Hidden',
    'summary': "AI Website Sale preview cards for website livechat",
    'depends': ['ai_website_livechat', 'ai_website_sale'],
    'assets': {
        'web.assets_frontend': [
            'ai_website_sale_livechat/static/src/scss/ai_product_preview.scss',
            'ai_website_sale_livechat/static/src/interactions/*',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
