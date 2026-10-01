{
    'author': 'Odoo S.A.',
    'name': 'Guatemala - E-Invoicing',
    'icon': '/account/static/description/l10n.png',
    'category': 'Accounting/Localizations/EDI',
    'description': """
E-invoice implementation for Guatemala
    """,
    'website': 'https://www.odoo.com/documentation/latest/applications/finance/fiscal_localizations.html',
    'depends': [
        'account_debit_note',
        'account_tax_python',
        'l10n_gt',
    ],
    'data': [
        'data/l10n_gt_edi.phrase.csv',
        'data/res_partner_data.xml',
        'data/templates.xml',
        'views/account_move_views.xml',
        'views/account_tax_views.xml',
        'views/l10n_gt_edi_phrase_views.xml',
        'views/report_invoice.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'wizard/account_cancel_wizard_views.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/demo_gt.xml',
    ],
    'license': 'OEEL-1',
}
