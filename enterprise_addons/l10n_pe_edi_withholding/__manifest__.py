{
    'name': 'Peru - Withholding Documents',
    'countries': ['pe'],
    'category': 'Accounting/Localizations',
    'description': """
    """,
    'depends': ['l10n_pe_edi', 'l10n_account_withholding_tax'],
    'data': [
        'views/account_payment_views.xml',
        'views/report_withholding.xml',
        'wizards/account_payment_register_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
