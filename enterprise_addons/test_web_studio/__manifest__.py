
{
    'name': 'Web Studio Tests',
    'category': 'Hidden',
    'sequence': 9876,
    'summary': 'Web studio Test',
    'description': """This module contains tests related to web studio. Those are
present in a separate module as it contains models used only to perform
tests independently to functional aspects of other models. """,
    'depends': ['web_studio', 'website', 'sale'],
    'data': [
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    "assets": {
        'web.assets_tests': [
            'test_web_studio/static/tests/**/*',
        ],
    }
}
