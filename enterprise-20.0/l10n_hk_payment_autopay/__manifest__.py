# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "AutoPay Payments",
    "summary": """Export payments as AutoPay files""",
    "category": "Accounting/Accounting",
    "description": """
Export payments file for AutoPay file upload in Hong Kong.
    """,
    "depends": ["account_batch_payment", "l10n_hk", "l10n_hk_autopay"],
    "data": [
        "data/l10n_hk_payment_autopay.xml",
        "views/account_journal_views.xml",
        "views/account_payment_views.xml",
    ],
    "auto_install": ["l10n_hk", "l10n_hk_autopay"],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
