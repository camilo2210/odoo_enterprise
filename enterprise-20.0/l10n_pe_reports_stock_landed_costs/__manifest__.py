# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Peru - Stock Reports Landed Costs",
    "countries": ["pe"],
    "description": """
Bridge module to include landed costs as separate lines in the
Peruvian Kardex PLE 13.1 report (operation type 26).
    """,
    "author": "Vauxoo, Odoo SA",
    "category": "Accounting/Localizations/Reporting",
    "website": "https://www.odoo.com/app/accounting",
    "license": "OEEL-1",
    "depends": [
        "l10n_pe_reports_stock",
        "stock_landed_costs",
    ],
    "auto_install": True,
}
