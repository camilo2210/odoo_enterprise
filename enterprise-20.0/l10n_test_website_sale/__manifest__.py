{
    'name': "Test - Ecommerce & Accouting Localizations",
    'category': 'Hidden',
    'sequence': 9956,
    'summary': "Shop address Test for different countries",
    'description': """This module contains tests and tours related to shop address for different country localizations.""",
    'depends': [
        'l10n_br',
        'l10n_cl',
        'l10n_co_edi',
        'l10n_ec',
        'l10n_it_edi',
        'l10n_pe',
        'website_address_autocomplete',
        'website_sale',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_tests': [
            'l10n_test_website_sale/static/tests/tours/**/*',
        ],
    },
}
