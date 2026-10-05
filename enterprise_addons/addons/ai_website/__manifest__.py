{
    'name': "AI Website Integration",
    'category': 'Hidden',
    'summary': "AI website integration",
    'depends': ['ai', 'website', 'ai_html_builder', 'web_unsplash'],
    'data': [
        'data/ir_actions_server_data.xml',
        'data/ai_skill_data.xml',
        'data/website_ai_reviewer.xml',
        'data/website_ai_agent.xml',
        'data/ai_skill_webform_data.xml',
        'data/ai_composer_data.xml',
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
        'views/snippets/snippets.xml',
    ],
    'assets': {
        'ai_website.ai_assets': [
            'ai_website/static/src/public/ai_script_manager.js',
        ],
        # Only served to users who can open the builder.
        'ai_website.ai_editor_assets': [
            'ai_website/static/src/public/ai_script_tracking.js',
        ],
        'web.assets_backend': [
            'ai_website/static/src/utils.js',
            'ai_website/static/src/ai_processing_state.js',
            'ai_website/static/src/discuss/**/*',
        ],
        'website.assets_editor': [
            'ai_website/static/src/components/dialog/add_page_dialog.js',
            'ai_website/static/src/components/dialog/add_page_dialog.xml',
            'ai_website/static/src/components/dialog/seo_patch.js',
            'ai_website/static/src/components/dialog/seo_patch.xml',
        ],
        'website.website_builder_assets': [
            'ai_website/static/src/utils.js',
            'ai_website/static/src/ai_processing_state.js',
            'ai_website/static/src/builder/**/*',
            'ai_website/static/src/discuss/**/*',
            ('remove', 'ai_website/static/src/discuss/composer_patch.xml'),
            'ai_website/static/src/scss/element_selection.scss',
            'ai_website/static/src/xml/**/*',
        ],
        'website.assets_inside_builder_iframe': [
            'ai_website/static/src/scss/element_selection.scss',
        ],
        'web.assets_unit_tests': [
            'ai_website/static/tests/**/*',
            'ai_website/static/src/public/**/*',
            ('remove', 'ai_website/static/tests/tours/**/*'),
        ],
        'web.assets_tests': [
            'ai_website/static/tests/tours/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
