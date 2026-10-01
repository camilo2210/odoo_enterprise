# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Philippines - Accounting Inventory Report",
    "summary": "Inventory Accounting report for the Philippines",
    "category": "Accounting/Localizations/Reporting",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": [
        "l10n_ph_reports",
        "stock",
    ],
    "data": [
        "data/boa_inventory_report.xml",
        "views/pdf_export_template.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ph_reports_stock/static/src/components/**/*",
        ],
    },
    "auto_install": True,
}
