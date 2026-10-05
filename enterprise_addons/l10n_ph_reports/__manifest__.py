# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Philippines - Accounting Reports',
    "summary": "Accounting reports for the Philippines",
    "category": "Accounting/Localizations/Reporting",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": [
        "l10n_ph",
        "account_reports",
        "account_reports_cash_basis",
    ],
    "data": [
        "data/account_return_data.xml",
        "data/bir_2306_2307_report.xml",
        "data/bir_alphalist_reports.xml",
        "data/slsp_report.xml",
        "report/certificates_2306_2307_pdf_export_templates.xml",

        "data/mail_template_data.xml",
        "wizard/vat_report_export.xml",
        "data/account_move_actions.xml",
        "data/boa_general_journal_report.xml",
        "data/boa_aged_partner_balance_report.xml",
        "data/boa_cash_payment_report.xml",
        "data/boa_general_ledger_report.xml",
        "data/boa_sales_report.xml",
        "data/boa_purchases_report.xml",
        "data/menuitem_data.xml",
        "views/pdf_export_templates.xml",
        "views/res_partner_views.xml",
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_ph_reports/static/src/components/**/*',
        ],
        'account_reports.assets_pdf_export': [
            'l10n_ph_reports/static/src/components/bir_2306_2307_reports/bir_2306_2307_report.scss',
        ],
    },
    "auto_install": True,
}
