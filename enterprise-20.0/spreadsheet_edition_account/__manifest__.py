# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet edition account",
    'category': 'Productivity/Dashboard',
    'summary': 'Enable fiscal year global filter in spreadsheet edition',
    'description': 'Enable fiscal year global filter in spreadsheet edition',
    'depends': ['spreadsheet_edition', 'spreadsheet_account'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'spreadsheet.o_spreadsheet': [
            'spreadsheet_edition_account/static/src/bundle/**/*.js',
        ],
    }
}
