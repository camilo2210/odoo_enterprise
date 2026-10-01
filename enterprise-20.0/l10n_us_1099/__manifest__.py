 # Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "United States - 1099 Reporting",
    "summary": """Easily export 1099 data for e-filing with a 3rd party.""",
    "category": "Accounting/Accounting",
    "description": """
Allows users to easily export accounting data that can be imported to a 3rd party that does 1099 e-filing.
    """,
    "depends": [
        "l10n_us",
        "l10n_us_account",
        "account_accountant",  # because we rely on bank reconciliation
    ],
    "data": [
        "data/l10n_us.1099_box.csv",
        "views/res_partner_views.xml",
        "views/box_1099_views.xml",
        "wizard/generate_1099_wizard_views.xml",
        'security/ir.access.csv',
    ],
    "demo": [
        "demo/res_partner_demo.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "auto_install": True,
}
