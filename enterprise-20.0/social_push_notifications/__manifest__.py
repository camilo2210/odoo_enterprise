# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Social Push Notifications',
    'category': 'Marketing/Social Marketing',
    'summary': 'Send push notifications to your web visitors',
    'version': '1.1',
    'description': """Send push notifications to your web visitors""",
    'depends': ['social', 'website'],
    'data': [
        'views/website_templates.xml',
        'views/social_post_template_views.xml',
        'views/social_post_views.xml',
        'views/res_config_settings_views.xml',
        'views/social_push_notifications_templates.xml',
        'views/website_visitor_views.xml',
        'views/utm_campaign_views.xml',
        'data/social_media_data.xml',
        'data/utm_data.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'post_init_hook': '_create_social_accounts',
    'assets': {
        'social_push_notifications.assets_push_notifications': [
            'social_push_notifications/static/src/components/**/*',
            'social_push_notifications/static/src/interactions/**/*',
        ],
        'web.assets_backend': [
            'social_push_notifications/static/src/components/**/*',
            'social_push_notifications/static/src/views/**/*',
            'social_push_notifications/static/src/scss/social_push_notifications.scss',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
