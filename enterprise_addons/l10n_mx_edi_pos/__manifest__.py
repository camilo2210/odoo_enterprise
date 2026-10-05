# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Mexican Localization for the Point of Sale',
    'version': '0.1',
    'category': 'Accounting/Localizations/EDI',
    'description': """
    """,
    'depends': [
        'l10n_mx_edi',
        'point_of_sale',
    ],
    'data': [
        'security/ir.access.csv',

        'views/res_config_settings_views.xml',
        'views/pos_payment_method_views.xml',
        'views/res_partner_views.xml',
        'views/pos_order_views.xml',
        'views/pos_ticket_view.xml',

        'wizard/l10n_mx_edi_global_invoice_create.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n_mx_edi_pos/static/src/**/*',
        ],
        'web.assets_tests': [
            'l10n_mx_edi_pos/static/tests/tours/invoice_order_tour.js',
            'l10n_mx_edi_pos/static/tests/tours/invoice_previous_order_tour.js',
            'l10n_mx_edi_pos/static/tests/tours/l10n_mx_pos_tour.js',
            'l10n_mx_edi_pos/static/tests/tours/refund_order_tour.js',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
