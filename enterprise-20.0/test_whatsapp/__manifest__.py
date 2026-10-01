
{
    'name': 'WhatsApp Tests',
    'category': 'Hidden',
    'sequence': 9898,
    'summary': 'WhatsApp Tests',
    'description': """This module contains tests related to various whatsapp
features. Those tests are present in a separate module as it contains models
used only to perform tests independently to functional aspects of real
applications. """,
    'depends': [
        'contacts',
        'mail',
        'portal',
        'whatsapp',
    ],
    'data': [
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_tests': [
            'test_whatsapp/static/tests/tours/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
