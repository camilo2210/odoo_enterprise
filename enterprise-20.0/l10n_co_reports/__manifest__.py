# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (C) David Arnold (XOE Solutions).
# Author        David Arnold (XOE Solutions), dar@xoe.solutions
# Co-Authors    Juan Pablo Aries (devCO), jpa@devco.co
#               Hector Ivan Valencia Muñoz (TIX SAS)
#               Nhomar Hernandez (Vauxoo)
#               Humberto Ochoa (Vauxoo)

{
    'name': 'Colombian - Accounting Reports',
    'version': '1.1',
    'description': """
Accounting reports for Colombia
================================
    """,
    'author': 'David Arnold (XOE Solutions)',
    'category': 'Accounting/Localizations/Reporting',
    'depends': ['l10n_co', 'account_reports', 'l10n_co_edi'],
    'data': [
        'data/l10n_co_reports.xml',
        'data/l10n_co_reports_ica.xml',
        'data/l10n_co_reports_iva.xml',
        'data/l10n_co_reports_fuente.xml',
        'data/profit_loss_pymes.xml',
        'data/balance_sheet_pymes.xml',
        'data/trial_balance_per_partner.xml',
        'data/l10n_co_reports_libro_diario.xml',
        'data/l10n_co_reports_libro_inv_blc.xml',
        'data/res_currency_data.xml',
        'data/l10n_co.exogenous.category.csv',
        'data/l10n_co.exogenous.config.csv',
        'wizard/retention_report_views.xml',
        'wizard/exogenous_report_views.xml',
        'report/certification_report_templates.xml',
        'report/libro_diario_report_templates.xml',
        'views/account_account_views.xml',
        'views/l10n_co_exogenous_config_views.xml',
        'views/l10n_co_exogenous_category_views.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_co', 'account_reports', 'l10n_co_edi'],
    'website': 'https://xoe.solutions',
    'license': 'OEEL-1',
    'post_init_hook': '_post_init_hook',
}
