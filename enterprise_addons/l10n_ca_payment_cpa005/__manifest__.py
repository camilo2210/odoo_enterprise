# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "CPA005 Payments",
    "summary": """Export payments as CPA 005 AFT files""",
    "category": "Accounting/Accounting",
    "description": """
Export payments as CPA 005 files for use in Canada.
    """,
    "depends": [
        "account_direct_debit",
        "l10n_ca"
    ],
    "data": [
        "data/l10n_ca_payment_cpa005.xml",
        "data/l10n_ca_cpa005.transaction.code.csv",
        "data/cpa005_pad_mail_template.xml",
        "report/cpa005_pad_mandate_report.xml",
        "views/account_batch_payment_views.xml",
        "views/account_direct_debit_mandate_views.xml",
        "views/account_journal_views.xml",
        "views/account_payment_views.xml",
        "views/l10n_ca_cpa005_transaction_code_views.xml",
        "views/res_company_views.xml",
        "views/res_partner_bank_views.xml",
        "wizard/account_payment_register_views.xml",
        "security/ir.access.csv",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "auto_install": True,
}
