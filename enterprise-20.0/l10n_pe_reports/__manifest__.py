# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Peru - Accounting Reports',
    "description": """
Electronic accounting reports
    - Sales report
    - Purchase report

P&L + balance Sheet
    """,
    "author": "Vauxoo, Odoo S.A.",
    "category": "Accounting/Localizations/Reporting",
    "website": "https://www.odoo.com/app/accounting",
    "license": "OEEL-1",
    "depends": [
        "l10n_pe_edi",
        "account_reports",
    ],
    "data": [
        "data/balance_sheet.xml",
        "data/profit_loss.xml",
        "data/account_ple_purchase_8_1_report.xml",
        "data/account_ple_purchase_8_2_report.xml",
        "data/account_ple_sales_14_1_report.xml",
        "data/l10n_pe.ple.usage.csv",
        "data/res.country.csv",
        "data/tax_report.xml",
        "data/account_return_data.xml",
        "views/account_move_view.xml",
        "views/res_config_settings_views.xml",
        'security/ir.access.csv',
    ],
    "auto_install": True,
}
