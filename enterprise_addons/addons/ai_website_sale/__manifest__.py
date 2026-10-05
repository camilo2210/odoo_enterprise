# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Website Sale',
    'category': 'AI',
    'summary': "AI Website Sale",
    'depends': ['ai_website', 'website_sale', 'ai_product'],
    'data': [
        'data/ai_composer_data.xml',
        'data/product_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_website_sale/static/src/modules/mail/**/*',
            'ai_website_sale/static/src/modules/html_editor/**/*',
            'ai_website_sale/static/src/modules/web/**/*',
        ],
        'website.website_builder_assets': [
            'ai_website_sale/static/src/modules/website_builder/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
