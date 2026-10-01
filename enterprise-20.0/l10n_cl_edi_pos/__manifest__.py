
{
    'name': "Chilean module for Point of Sale",

    'summary': "Chilean module for Point of Sale",

    'description': """
This module brings the technical requirement for the Chilean regulation.
Install this if you are using the Point of Sale app in Chile.

""",

    'category': 'Accounting/Localizations/Point of Sale',

    'depends': ['l10n_cl_edi', 'point_of_sale'],
    'auto_install': True,
    'data': [
        'views/pos_order_views.xml',
        'views/res_partner_views.xml',
        'receipt/pos_order_receipt.xml',
    ],
    'assets': {
        'web.assets_unit_tests': [
            'l10n_cl_edi_pos/static/tests/unit/**/*',
        ],
        'point_of_sale._assets_pos': [
            'l10n_cl_edi_pos/static/src/**/*'
        ],
        'web.assets_tests': [
            'l10n_cl_edi_pos/static/tests/tours/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
