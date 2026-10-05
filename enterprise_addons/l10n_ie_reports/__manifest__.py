# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Ireland - Accounting Reports",
    "category": "Accounting/Localizations/Reporting",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": [
        "l10n_ie",
        "account_reports",
    ],
    "data": [
        "data/profit_and_loss-ie.xml",
        "data/profit_and_loss_tags-ie.xml",
        "data/balance_sheet-ie.xml",
        "data/balance_sheet_tags-ie.xml",
        "data/ec_sales_list_report-ie.xml",
        "data/tax_report-ie.xml",
        "data/vat3_template.xml",
        "data/account_return_data.xml",
    ],
    "auto_install": ["l10n_ie", "account_reports"],
}
