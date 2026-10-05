
{
    'name': "Germany - Certification for Point of Sale",
    'summary': "Germany TSS Regulation",

    'description': """
This module brings the technical requirement for the new Germany regulation with the Technical Security System by using a cloud-based solution with Fiskaly.

Install this if you are using the Point of Sale app in Germany.

""",

    'category': 'Accounting/Localizations/Point of Sale',
    'version': '0.1',

    'depends': ['l10n_de', 'point_of_sale', 'iap'],
    'auto_install': True,

    'data': [
        'views/account_view.xml',
        'views/l10n_de_pos_dsfinvk_export_views.xml',
        'views/l10n_de_pos_tss_export_views.xml',
        'views/menuitems_views.xml',
        'views/point_of_sale_dashboard.xml',
        'views/res_config_settings_views.xml',
        'views/pos_order_views.xml',
        'views/res_company_views.xml',
        'receipt/pos_order_receipt.xml',

        'security/ir.access.csv',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n_de_pos_cert/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'l10n_de_pos_cert/static/tests/unit/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
