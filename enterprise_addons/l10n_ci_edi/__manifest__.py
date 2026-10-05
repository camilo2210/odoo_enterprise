# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Ivory Coast - E-Invoicing (FNE)",
    'summary': "Ivory Coast Facture Normalisée Electronique (FNE) Integration",
    'description': """
        This module integrates with the Ivory Coast's Direction Générale des Impôts (DGI)
        electronic invoicing system (Facture Normalisée Electronique - FNE).

        It allows companies to:
        - Send normalized invoices electronically to the DGI
        - Receive validation and normalized invoice numbers
        - Generate QR codes for validated invoices
        - Handle credit notes and invoice corrections
    """,
    'author': 'Odoo S.A.',
    'category': 'Accounting/Localizations/EDI',
    'license': 'OEEL-1',
    'depends': ['l10n_ci'],
    'data': [
        'data/res_partner_category_data.xml',
        'views/account_move_views.xml',
        'views/account_tax_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'auto_install': ['l10n_ci'],
}
