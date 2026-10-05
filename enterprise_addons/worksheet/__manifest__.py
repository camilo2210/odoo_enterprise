# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Worksheet',
    'category': 'Hidden',
    'summary': 'Create worksheet with property field',
    'description': """Create worksheet with property field""",
    'data': [
        'views/worksheet_template_properties_display.xml',
        'views/worksheet_template_view.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'worksheet/static/src/components/**/*',
            'worksheet/static/src/views/**/*',
        ],
        'web.assets_frontend': [
            'worksheet/static/src/scss/worksheet_portal.scss',
        ],
        'web.report_assets_common': [
            'worksheet/static/src/scss/worksheet_portal.scss',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
