# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Odoo Mexican Localization Reports",
    "description": """
Electronic accounting reports
    - COA
    - Trial Balance
    - Month 13 Trial Balance
    - XML Polizas Export

DIOT Report
    """,
    "author": "Vauxoo / Odoo S.A.",
    "category": "Accounting/Localizations/Reporting",
    "website": "https://www.vauxoo.com",
    "license": "OEEL-1",
    "depends": [
        "account_reports",
        "l10n_mx",
        "l10n_mx_edi",
    ],
    "data": [
        "data/account_report_diot.xml",
        "data/profit_and_loss_mx_nif_b3.xml",
        "data/balance_sheet_mx_nif_b6.xml",
        "data/account_return_data.xml",
        "data/country_data.xml",
        "data/templates/cfdicoa.xml",
        "data/templates/cfdibalance.xml",
        "data/templates/xml_polizas.xml",
        "views/account_views.xml",
        "views/account_move_views.xml",
        "views/res_country_view.xml",
        "views/res_partner_view.xml",
        "wizard/xml_polizas_wizard_view.xml",
        "wizard/sat_export_wizard_view.xml",
        'security/ir.access.csv',
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_mx_reports/static/src/components/**/*",
        ],
        "web.assets_tests": [
            "l10n_mx_reports/static/tests/tours/*",
        ],
    },
    "auto_install": ['l10n_mx', 'account_reports'],
}
