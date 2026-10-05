# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2008-2010 Zikzakmedia S.L. (http://zikzakmedia.com) All Rights Reserved.
#                         Jordi Esteve <jesteve@zikzakmedia.com>
# Copyright (c) 2012-2013, Grupo OPENTIA (<http://opentia.com>) Registered EU Trademark.
#                         Dpto. Consultoría <consultoria@opentia.es>
# Copyright (c) 2013 Serv. Tecnol. Avanzados (http://www.serviciosbaeza.com)
#                    Pedro Manuel Baeza <pedro.baeza@serviciosbaeza.com>


{
    'name': 'Spain - Accounting Reports',
    'version': '4.3',
    'author': 'Spanish Localization Team',
    'website': 'https://launchpad.net/openerp-spain',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Spain
    """,
    'depends': [
        'l10n_es', 'account_reports',
    ],
    'data': [
        'views/account_invoice_views.xml',
        'views/res_company_views.xml',
        'views/account_return_views.xml',
        'data/pymes_profit_and_loss_report_data.xml',
        'data/assoc_balance_sheet_report_data.xml',
        'data/account_tags.xml',
        'data/abbreviated_balance_sheet_report_data.xml',
        'data/abbreviated_profit_and_loss_report_data.xml',
        'data/full_balance_sheet_report_data.xml',
        'data/full_profit_and_loss_report_data.xml',
        'data/pymes_balance_sheet_report_data.xml',
        'data/mod111.xml',
        'data/mod115.xml',
        'data/mod130.xml',
        'data/mod303.xml',
        'data/mod347.xml',
        'data/mod349.xml',
        'data/mod390.xml',
        'data/trial_balance.xml',
        'data/vat_books_report.xml',
        'data/menuitem_data.xml',
        'wizard/aeat_return_submission_wizard.xml',
        'data/account_return_data.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_es', 'account_reports'],
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'l10n_es_reports/static/src/**/*',
        ],
    },
}
