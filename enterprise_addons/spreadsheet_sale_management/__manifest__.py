# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Sale order spreadsheet",
    'category': 'Sales/Sales',
    'description': 'Link a spreadsheet to a quotation templates and access your calculator from a Sale Order.',
    'depends': ['spreadsheet_edition', 'sale_management'],
    'auto_install': ['sale_management'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'views/sale_order_template_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_spreadsheet_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'spreadsheet.o_spreadsheet': [
            'spreadsheet_sale_management/static/src/bundle/**/*.js',
            'spreadsheet_sale_management/static/src/bundle/**/*.xml',
        ],
        'web.assets_backend': [
            'spreadsheet_sale_management/static/src/assets/**/*.js',
        ],
        'web.assets_unit_tests': [
            'spreadsheet_sale_management/static/tests/**/*',
        ],
    },
    'demo': [
        'demo/sale_order_spreadsheet_demo.xml',
        'demo/sale_order_template_demo.xml',
    ]
}
