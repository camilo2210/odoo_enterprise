# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Documents Testing Module',
    'category': 'Hidden/Tests',
    'sequence': 9999,
    'summary': 'Documents Testing Module',
    'website': 'https://www.odoo.com/app/documents',
    'depends': [
        'documents',
        'documents_account',
        'knowledge',
        'l10n_be_codabox',
        'test_mail',
    ],
    'data': [
        'data/documents_folder_data.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_unit_tests': [
            'test_documents_full/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
