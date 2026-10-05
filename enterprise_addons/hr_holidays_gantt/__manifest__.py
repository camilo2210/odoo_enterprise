{
    'name': "Time off Gantt",
    'summary': """Gantt view for Time Off Dashboard""",
    'description': """
    Gantt view for Time Off Dashboard
    """,
    'category': 'Human Resources',
    'depends': ['base_import', 'hr_holidays', 'hr_gantt'],
    'auto_install': True,
    'data': [
        'views/hr_holidays_gantt_view.xml',
    ],
    'assets': {
        "im_livechat.assets_embed_core": [
            "hr_holidays_gantt/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "hr_holidays_gantt/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "hr_holidays_gantt/static/src/core/common/**/*",
        ],
        'web.assets_backend': [
            "hr_holidays_gantt/static/src/core/common/**/*",
            'hr_holidays_gantt/static/src/core/web/avatar_card/hr_holidays_gantt_avatar_card.js',
            'hr_holidays_gantt/static/src/core/web/avatar_card/hr_holidays_gantt_avatar_card.xml',
            'hr_holidays_gantt/static/src/views/gantt/hr_holidays_gantt_cog_menu.js',
        ],
        'web.assets_backend_lazy': [
            'hr_holidays_gantt/static/src/**/*',
            ('remove', 'hr_holidays_gantt/static/src/views/gantt/hr_holidays_gantt_cog_menu.js'),
        ],
        'web.assets_unit_tests': [
            'hr_holidays_gantt/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
