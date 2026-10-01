# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'LNE electronic scale certification for PoS',
    'category': 'Sales/Point of Sale',
    'summary': 'Ensure scale measurements conform to EU certification standards.',
    'description': """
This module certifies the Point of Sale with the LNE (Laboratoire national de métrologie et d'essais),
a legal requirement in certain EU countries. It enforces certain settings and provides a checksum that
can be verified to make sure the code has not been tampered with.
""",
    'depends': ['pos_iot'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'receipt/pos_order_receipt.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n_eu_iot_scale_cert/static/src/app/**/*',
            'l10n_eu_iot_scale_cert/static/src/pos_overrides/**/*',
        ],
        'point_of_sale.customer_display_assets': [
            'l10n_eu_iot_scale_cert/static/src/customer_display_overrides/**/*',
        ],
        'web.assets_unit_tests': [
            'l10n_eu_iot_scale_cert/static/tests/unit/**/*',
        ],
    }
}
