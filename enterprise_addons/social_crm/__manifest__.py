# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Leads statistics and generation on social',
    'category': 'Marketing/Social Marketing',
    'summary': 'Add crm UTM info on social',
    'description': """UTM and posts on crm""",
    'depends': ['social', 'crm'],
    'data': [
        'data/social_post_to_lead_templates.xml',
        'views/social_post_views.xml',
        'wizard/social_post_to_lead_views.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            ('after', 'social/static/src/js/stream_post_comment.js', 'social_crm/static/src/js/stream_post_comment.js'),
            ('after', 'social/static/src/js/stream_post_comments.js', 'social_crm/static/src/js/stream_post_comments.js'),
            'social_crm/static/src/xml/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
