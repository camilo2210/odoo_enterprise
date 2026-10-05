{
    "name": "Romania - D300 VAT Report",
    "description": """
        D300 VAT declaration export for Romania (ANAF).
    """,
    "depends": [
        "l10n_ro_reports",
    ],
    "data": [
        "data/account_tax_report_data.xml",
        "wizard/d300_submission_wizard_views.xml",
        'security/ir.access.csv',
    ],
    "auto_install": True,
    "post_init_hook": "_post_init_hook",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
