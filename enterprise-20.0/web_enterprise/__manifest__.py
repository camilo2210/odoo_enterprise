# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Web Enterprise',
    'category': 'Hidden',
    'description': """
Odoo Enterprise Web Client.
===========================

This module modifies the web addon to provide Enterprise design and responsiveness.
        """,
    'depends': ['web', 'base_setup'],
    'auto_install': ['web'],
    'data': [
        'views/webclient_templates.xml',
        'views/res_config_settings.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('after', 'web/static/src/scss/primary_variables.scss', 'web_enterprise/static/src/**/*.variables.scss'),
            ('before', 'web/static/src/scss/primary_variables.scss', 'web_enterprise/static/src/scss/primary_variables.scss'),
        ],
        'web._assets_secondary_variables': [
            ('before', 'web/static/src/scss/secondary_variables.scss', 'web_enterprise/static/src/scss/secondary_variables.scss'),
        ],
        'web._assets_backend_helpers': [
            ('before', 'web/static/src/scss/bootstrap_overridden.scss', 'web_enterprise/static/src/scss/bootstrap_overridden.scss'),
        ],
        'web.assets_frontend': [
            'web_enterprise/static/src/webclient/home_menu/home_menu_background.scss', # used by login page
            'web_enterprise/static/src/webclient/navbar/navbar.scss',
        ],
        'web.assets_backend': [
            'web_enterprise/static/src/webclient/**/*.scss',
            'web_enterprise/static/src/views/**/*.scss',

            'web_enterprise/static/src/core/**/*',
            'web_enterprise/static/src/webclient/**/*.js',
            ('after', 'web/static/src/views/list/list_renderer.xml', 'web_enterprise/static/src/views/list/list_renderer_desktop.xml'),
            ('after', 'web/static/src/views/kanban/kanban_renderer.xml', 'web_enterprise/static/src/views/kanban/kanban_renderer.xml'),
            ('after', 'web/static/src/views/kanban/kanban_header.xml', 'web_enterprise/static/src/views/kanban/kanban_header.xml'),
            ('after', 'web/static/src/views/widgets/ribbon/ribbon.xml', 'web_enterprise/static/src/views/widgets/ribbon/ribbon.xml'),
            ('after', 'web/static/src/views/calendar/calendar_controller.xml', 'web_enterprise/static/src/views/calendar/calendar_controller.xml'),
            ('after', 'web/static/src/views/calendar/calendar_side_panel/calendar_side_panel.xml', 'web_enterprise/static/src/views/calendar/calendar_side_panel/calendar_side_panel.xml'),
            'web_enterprise/static/src/webclient/**/*.xml',
            'web_enterprise/static/src/views/**/*.js',
            'web_enterprise/static/src/views/**/*.xml',
            'web_enterprise/static/src/search/**/*.js',
            'web_enterprise/static/src/search/**/*.scss',
            ('after', '/web/static/src/search/control_panel/control_panel.xml', 'web_enterprise/static/src/search/control_panel/control_panel.xml'),
            ('remove', 'web_enterprise/static/src/views/pivot/**'),
            ('remove', 'web_enterprise/static/src/views/graph/**'),

            # Don't include dark mode files in light mode
            ('remove', 'web_enterprise/static/src/**/*.dark.scss'),
        ],
        'web.assets_backend_lazy': [
            'web_enterprise/static/src/views/pivot/**',
            'web_enterprise/static/src/views/graph/**',
        ],
        'web.assets_backend_lazy_dark': [
            ('include', 'web.dark_mode_variables'),
            # web._assets_backend_helpers
            ('before', 'web_enterprise/static/src/scss/bootstrap_overridden.scss', 'web_enterprise/static/src/scss/bootstrap_overridden.dark.scss'),
            ('after', 'web/static/lib/bootstrap/scss/_functions.scss', 'web_enterprise/static/src/scss/bs_functions_overridden.dark.scss'),
        ],
        'web.assets_web': [
            ('replace', 'web/static/src/main.js', 'web_enterprise/static/src/main.js'),
        ],
        # ========= Dark Mode =========
        "web.dark_mode_variables": [
            # web._assets_primary_variables
            ('before', 'web_enterprise/static/src/scss/primary_variables.scss', 'web_enterprise/static/src/scss/primary_variables.dark.scss'),
            ('before', 'web_enterprise/static/src/**/*.variables.scss', 'web_enterprise/static/src/**/*.variables.dark.scss'),
            # web._assets_secondary_variables
            ('before', 'web_enterprise/static/src/scss/secondary_variables.scss', 'web_enterprise/static/src/scss/secondary_variables.dark.scss'),
        ],
        "web.assets_web_dark": [
            ('include', 'web.dark_mode_variables'),
            # web._assets_backend_helpers
            ('before', 'web_enterprise/static/src/scss/bootstrap_overridden.scss', 'web_enterprise/static/src/scss/bootstrap_overridden.dark.scss'),
            ('after', 'web/static/lib/bootstrap/scss/_functions.scss', 'web_enterprise/static/src/scss/bs_functions_overridden.dark.scss'),
            # assets_backend
            'web_enterprise/static/src/**/*.dark.scss',
        ],
        "web.assets_tests": [
            "web_enterprise/static/tests/tours/**/*.js",
        ],
        # Unit test files
        'web.assets_unit_tests': [
            'web_enterprise/static/tests/**/*.test.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
