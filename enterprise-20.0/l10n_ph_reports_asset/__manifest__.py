# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Philippines - Accounting Asset Report",
    "summary": "Fixed Asset Listing report for the Philippines",
    "category": "Accounting/Localizations/Reporting",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": [
        "l10n_ph_reports",
        "account_asset",
    ],
    "data": [
        "views/account_asset_inherit_views.xml",
        "data/boa_fal_report.xml",
        "data/pdf_export_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ph_reports_asset/static/src/components/**/*",
        ],
    },
    "auto_install": True,
}
