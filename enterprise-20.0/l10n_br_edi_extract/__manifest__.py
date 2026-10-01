# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Brazil - NFS-e Bill OCR",
    "summary": "OCR support for NFS-e Vendor Bills for Brazil Localization",
    "description": """
Brazil - NFS-e Bill OCR
========================
Extract NFS-e vendor bills using OCR to fill them automatically,
""",
    "category": "Accounting/Localizations",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": ["l10n_br_edi", "account_invoice_extract"],
    "auto_install": True,
}
