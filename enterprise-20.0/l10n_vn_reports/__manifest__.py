# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Vietnam - Accounting Reports',
    "summary": "Accounting reports for the Vietnam",
    "category": "Accounting/Localizations/Reporting",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": [
        "l10n_vn",
        "account_reports",
    ],
    "data": [
        "data/account_tax_report_data.xml",
        "data/account_return_data.xml",
        "data/balance_sheet.xml",
        "data/general_ledger.xml",
        "data/general_journal.xml",
        "data/profit_and_loss.xml",
        "report/form_01_gtgt_xml_template.xml",
        "wizard/tax_report_xml_export_wizard_views.xml",
        'security/ir.access.csv',
    ],
    "auto_install": True,
    'assets': {
        'web.assets_backend': [
            'l10n_vn_reports/static/src/components/**/*',
        ]
    }
}
