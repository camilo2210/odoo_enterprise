# Part of Odoo. See LICENSE file for full copyright and licensing details.

{

    'name': 'Bulgarian Standard Audit File for Tax',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'icon': '/account/static/description/l10n.png',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Bulgarian SAF-T is standard file format for exporting various types of accounting transactional data using the XML format.
""",
    'depends': [
        'l10n_bg',
        'l10n_bg_ledger',
        'account_saft',
        'account_intrastat',
        'accountant',
    ],
    'data': [
        'data/uom.uom.csv',
        'data/saft_report.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/account_tax_views.xml',
        'views/account_account_views.xml',
        'views/uom_uom_views.xml',
        'views/res_partner_bank_views.xml',
        'wizard/l10n_bg_saft_file_attachment_error_wizard.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],

    'post_init_hook': 'post_init_hooks',
    'auto_install': [
        'l10n_bg',
        'accountant',
    ],


}
