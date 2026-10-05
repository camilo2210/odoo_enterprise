# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Product',
    'category': 'AI',
    'summary': "AI Product",
    'depends': ['ai', 'product'],
    'data': [
        'data/product_views.xml',
        'data/ai_composer_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_product/static/src/modules/mail/**/*',
            'ai_product/static/src/modules/html_editor/**/*',
            'ai_product/static/src/modules/web/**/*',
        ]
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
