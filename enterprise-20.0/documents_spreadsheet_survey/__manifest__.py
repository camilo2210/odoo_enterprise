# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Spreadsheet Survey",
    'author': 'Odoo S.A.',
    'category': 'Productivity/Documents',
    'summary': 'Spreadsheet for Survey results',
    'description': 'Spreadsheet for Survey results',
    'depends': ['documents_spreadsheet', 'survey'],
    'data': [
        'views/survey_templates_statistics.xml',
        'views/survey_survey_views.xml',
    ],
    'auto_install': True,
    'license': 'OEEL-1',
    'assets': {
        'spreadsheet.o_spreadsheet_core': [
            'documents_spreadsheet_survey/static/src/spreadsheet/*.js',
        ],
        'web.assets_unit_tests': [
            'documents_spreadsheet_survey/static/tests/**/*',
        ]
    }
}
