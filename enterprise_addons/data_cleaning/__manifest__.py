# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Data Cleaning',
    'version': '1.1',
    'category': 'Productivity/Data Cleaning',
    'sequence': 135,
    'summary': """Easily format text data across multiple records. Find duplicate records and easily merge them.""",
    'description': """Easily format text data across multiple records. Find duplicate records and easily merge them.""",
    'depends': ['data_recycle', 'phone_validation', 'mail'],
    'data': [
        'views/data_cleaning_model_views.xml',
        'views/data_cleaning_rule_views.xml',
        'views/data_cleaning_record_views.xml',
        'views/data_cleaning_templates.xml',
        'views/data_merge_rule_views.xml',
        'views/data_merge_model_views.xml',
        'views/data_merge_record_views.xml',
        'views/menu_views.xml',
        'views/ir_model_views.xml',
        'data/data_cleaning_data.xml',
        'data/data_cleaning_cron.xml',
        'data/ir_model_data.xml',
        'data/mail_templates.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['data_recycle'],
    'assets': {
        'web.assets_backend': [
            'data_cleaning/static/src/**/*.js',
            'data_cleaning/static/src/**/*.xml',
            'data_cleaning/static/src/**/*.scss',
        ],
        'web.assets_unit_tests': [
            'data_cleaning/static/tests/*.test.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
