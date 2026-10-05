# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Thailand - Accounting Reports",
    "author": "Odoo S.A.",
    'category': 'Accounting',
    "description": """
Accounting reports for Thailand
==============================================================================
    """,
    "depends": [
        "l10n_th",
        "account_reports",
    ],
    "data": [
        "data/account_return_data.xml",
        "data/account_tax_report_data.xml",
    ],
    'auto_install': True,
    'license': 'OEEL-1',
}
