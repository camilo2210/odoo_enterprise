
{
    'name': 'Social Tests (Full)',
    'category': 'Hidden',
    'sequence': 9878,
    'summary': 'Social Tests: tests specific to social with all sub-modules',
    'description': """This module contains tests related to various social features
and social-related sub modules. It will test interactions between all those modules.""",
    'depends': [
        'ai_social',
        'social_facebook',
        'social_instagram',
        'social_linkedin',
        'social_push_notifications',
        'social_twitter',
        'social_youtube',
        'social_crm',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_unit_tests': [
            'social_test_full/static/tests/**/*',
        ]
    }
}
