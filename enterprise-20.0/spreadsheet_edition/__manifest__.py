# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet',
    'description': 'Spreadsheet',
    'depends': ['spreadsheet', 'mail', 'web_enterprise'],
    'data': [
        'views/spreadsheet_views.xml',
        'data/mail_template_layouts.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'spreadsheet.o_spreadsheet_core': [
            'web/static/src/views/pivot/pivot_arch_parser.js',
            'spreadsheet_edition/static/src/bundle/**/*.js',
            'spreadsheet_edition/static/src/bundle/**/filter_editor_side_panel.xml',
            'spreadsheet_edition/static/src/bundle/**/*.xml',
            ('remove', 'spreadsheet_edition/static/src/bundle/pivot/pivot.xml'),
        ],
        'web.assets_backend': [
            'spreadsheet_edition/static/src/bundle/**/*.scss',
            'spreadsheet_edition/static/src/bundle/**/*.css',
            'spreadsheet_edition/static/src/assets/**/*',
            ('remove', 'spreadsheet_edition/static/src/assets/graph_view/**'),
            ('remove', 'spreadsheet_edition/static/src/assets/pivot_view/**'),
        ],
        'web.assets_backend_lazy': [
            'spreadsheet_edition/static/src/assets/graph_view/**',
            'spreadsheet_edition/static/src/assets/pivot_view/**',
            'spreadsheet_edition/static/src/bundle/pivot/pivot.xml',
        ],
        'spreadsheet.public_spreadsheet': [
            'spreadsheet_edition/static/src/**/*.css',
            'spreadsheet_edition/static/src/public_spreadsheet/*',
            'spreadsheet_edition/static/src/public_spreadsheet/**/*',
            ('remove', 'spreadsheet_edition/static/src/bundle/components/spreadsheet_navbar/*'),
            ('remove', 'spreadsheet_edition/static/src/bundle/comments/*.js'),
            ('remove', 'spreadsheet_edition/static/src/bundle/comments/**/*.js'),
            ('remove', 'spreadsheet_edition/static/src/bundle/actions/*.js'),
            ('remove', 'spreadsheet_edition/static/src/bundle/actions/**/*.js'),
            ('remove', 'spreadsheet_edition/static/src/bundle/version_history/*.js'),
            ('remove', 'spreadsheet_edition/static/src/bundle/version_history/**/*.js'),
            ('remove', 'spreadsheet_edition/static/src/bundle/chart/**/*'),
        ],
        'web.assets_unit_tests': [
            'spreadsheet_edition/static/tests/**/*',
            'spreadsheet_edition/static/src/public_spreadsheet/**/*.js',
            'spreadsheet_edition/static/src/public_spreadsheet/**/*.xml',
        ],
    }
}
