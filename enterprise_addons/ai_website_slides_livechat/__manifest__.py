# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": 'AI Website Slides Livechat',
    "category": 'Hidden',
    "summary": "AI Website Slides preview cards for website livechat",
    "depends": ['ai_website_livechat', 'website_slides'],
    'assets': {
        'web.assets_frontend': [
            'ai_website_slides_livechat/static/src/scss/ai_slides_preview.scss',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
