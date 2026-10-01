# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet dashboard edition",
    'category': 'Productivity/Dashboard',
    'summary': 'Spreadsheet Dashboard edition',
    'description': 'Spreadsheet Dashboard edition',
    'depends': ['spreadsheet_dashboard', 'spreadsheet_edition'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        "views/spreadsheet_dashboard_views.xml",
        'security/ir.access.csv',
    ],
    'assets': {
        'spreadsheet.o_spreadsheet': [
            'spreadsheet_dashboard_edition/static/src/bundle/**/*.js',
        ],
        'web.assets_backend': [
            'spreadsheet_dashboard_edition/static/src/assets/**/*.js',
            'spreadsheet_dashboard_edition/static/src/**/*.scss',
            'spreadsheet_dashboard_edition/static/src/**/*.xml',
        ],
        'web.assets_unit_tests': [
            'spreadsheet_dashboard_edition/static/tests/**/*',
        ],
    }
}
