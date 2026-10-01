# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet Accounting Reports",
    'category': 'Accounting',
    'summary': 'Spreadsheet integration with Accounting Reports',
    'description': 'Adds integrations with accounting reports and working files.',
    'depends': ['spreadsheet', 'account_reports'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'security/ir.access.csv',
        'views/account_audit_views.xml',
    ],
    'assets': {
        'spreadsheet.o_spreadsheet': [
            'account_reports_spreadsheet/static/src/bundle/**/*.js',
            'account_reports_spreadsheet/static/src/bundle/**/*.xml',
        ],
        'web.assets_backend': [
            'account_reports_spreadsheet/static/src/**/*',
            ('remove', 'account_reports_spreadsheet/static/src/bundle/**/*'),
            'account_reports_spreadsheet/static/src/spreadsheet_action_loader.js',
        ],
        'web.assets_tests': [
            'account_reports_spreadsheet/static/tests/tours/**/*',
        ],
    },
}
