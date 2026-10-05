# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Planning",
    'summary': """Manage your employees' schedule""",
    'description': """
Schedule your teams and employees with shift.
    """,
    'category': 'Human Resources/Planning',
    'sequence': 130,
    'website': 'https://www.odoo.com/app/planning',
    'depends': ['hr', 'web_gantt', 'digest'],
    'data': [
        'security/planning_security.xml',
        'data/digest_data.xml',
        'data/planning_shift_template_data.xml',
        'wizard/planning_send_views.xml',
        'views/hr_views.xml',
        'views/planning_template_views.xml',
        'views/resource_views.xml',
        'views/planning_views.xml',
        'views/planning_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/planning_templates.xml',
        'report/planning_report_templates.xml',
        'report/planning_report_views.xml',
        'data/planning_cron.xml',
        'data/mail_template_data.xml',
        'data/planning_tour.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/planning_demo.xml',
    ],
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'planning/static/src/components/**/*',
            'planning/static/src/core/common/**/*',
            "planning/static/src/core/web/**/*",
            'planning/static/src/views/**/*',
            'planning/static/src/scss/planning_gantt.scss',
            'planning/static/src/scss/planning_list.scss',
            'planning/static/src/js/tours/planning.js',
            ('remove', 'planning/static/src/views/planning_graph/**'),
            ('remove', 'planning/static/src/views/planning_pivot/**'),
            ('remove', 'planning/static/src/views/planning_gantt/**'),
            ('remove', 'planning/static/src/views/planning_slot_analysis_graph/**'),
            ('remove', 'planning/static/src/views/planning_slot_analysis_pivot/**'),
            ('remove', 'planning/static/src/views/planning_slot_analysis_renderer_mixin.js'),
        ],
        'web.assets_backend_lazy': [
            'planning/static/src/views/planning_graph/**',
            'planning/static/src/views/planning_pivot/**',
            'planning/static/src/views/planning_gantt/**',
            'planning/static/src/views/planning_slot_analysis_graph/**',
            'planning/static/src/views/planning_slot_analysis_pivot/**',
            'planning/static/src/views/planning_slot_analysis_renderer_mixin.js',
        ],
        'im_livechat.assets_embed_core': [
            'planning/static/src/core/common/**/*',
        ],
        'mail.assets_public': [
            'planning/static/src/core/common/**/*',
        ],
        'portal.assets_chatter_helpers': [
            'planning/static/src/core/common/**/*',
        ],
        'web.assets_unit_tests': [
            'planning/static/tests/**/*',
        ],
        'web.assets_tests': [
            'planning/static/tests/tours/*',
        ],
    }
}
