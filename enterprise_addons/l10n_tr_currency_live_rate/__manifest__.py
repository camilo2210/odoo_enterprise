# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Türkiye - Live Currency Exchange Rate (Buying/Selling)",
    "category": "Accounting/Localizations",
    "countries": ["tr"],
    "summary": "Fetch and apply the buying/selling exchange rates published by the TCMB",
    "description": """
The TCMB publishes a separate buying and selling exchange rate per currency,
while Odoo only keeps a single rate. Turkish accounting needs the buying or
selling rate applied explicitly, instead of a single averaged one.

This module fetches both rates from the TCMB feed and lets the buying or the
selling one be picked on invoices, bills and payments.
""",
    "depends": [
        "l10n_tr",
        "currency_rate_live",
    ],
    "data": [
        "views/res_currency_views.xml",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/res_partner_views.xml",
        "wizard/account_payment_register_views.xml",
    ],
    "pre_init_hook": "_pre_init_hook",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
