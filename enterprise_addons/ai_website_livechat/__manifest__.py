# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "AI Website Livechat Integration",
    'category': 'Hidden',
    'summary': "AI website livechat components for web builder",
    'depends': ['ai_website', 'ai_livechat'],
    'data': [
        'views/snippets/snippets.xml',
        'views/snippets/s_ai_livechat.xml',
    ],
    'assets': {
        'im_livechat.assets_embed_core': [
            'ai_website_livechat/static/src/discuss/core/common/**/*',
            'ai_website_livechat/static/src/discuss/embed/common/**/*',
        ],
        "mail.assets_public": [
            "ai_website_livechat/static/src/discuss/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "ai_website_livechat/static/src/discuss/core/common/**/*",
        ],
        "web.assets_backend": [
            "ai_website_livechat/static/src/discuss/core/common/**/*",
        ],
        'im_livechat.assets_embed_cors': [
            'ai_website_livechat/static/src/discuss/embed/cors/**/*',
        ],
        'web.assets_frontend': [
            'web/static/lib/dompurify/DOMpurify.js',
            'ai_website_livechat/static/src/discuss/core/common/preview_records/**/*',
            'ai_website_livechat/static/src/website/components/**/*',
            'ai_website_livechat/static/src/website/interactions/*',
        ],
        'website.assets_inside_builder_iframe': [
            'ai_website_livechat/static/src/website/interactions/edit/**/*',
        ],
        'website.website_builder_assets': [
            'ai_website_livechat/static/src/website/plugins/**/*',
        ],
        'web.assets_unit_tests_setup': [
            'ai_website_livechat/static/src/discuss/core/common/preview_records/**/*',
        ],
        'web.assets_tests': [
            'ai_website_livechat/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'ai_website_livechat/static/tests/**/*.test.js',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
