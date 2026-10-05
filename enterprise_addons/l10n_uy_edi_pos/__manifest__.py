{
    "name": "Uruguay - Electronic Invoicing for POS",
    "countries": ["uy"],
    "category": "Accounting/Localizations/Point of Sale",
    "license": "OEEL-1",
    "description": """
Uruguayan electronic invoicing (CFE via Uruware) for the Point of Sale.

Orders whose customer is identified with a RUT are invoiced through the standard e-Invoice
pipeline (account.move). Any other order (CI/DNI/passport/none/Consumidor Final) issues an
e-Ticket (or e-Ticket Credit Note for refunds) directly from the pos.order.
    """,
    "author": "Odoo S.A.",
    "depends": [
        "l10n_uy_edi",
        "point_of_sale",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/pos_order_views.xml",
        "views/pos_ticket_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_uy_edi_pos/static/src/**/*",
        ],
    },
    "auto_install": True,
}
