# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Poland - Accounting Reports',
    'description': """
Accounting reports for Poland

        This module also provides the possibility to generate the JPK_VAT in xml, for Poland.

        Currently, does not report specific values for :
        - Cash basis for entries with input tax (MK)
        - Margin-based operations (MR_T/MR_UZ)
        - Bills for agricultural products (VAT_RR)
        - Operations through electronic interfaces (IED)
        - Invoices done with KSef
    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': [
        'l10n_pl',
        'l10n_pl_edi',
        'account_reports',
        'account_saft',
    ],
    'data': [
        'views/l10n_pl_wizard_xml_export_options_views.xml',
        'data/account_return_data.xml',
        'data/jpk_export_templates.xml',
        'data/tax_report.xml',
        'data/profit_loss_small.xml',
        'data/profit_loss_micro.xml',
        'data/balance_sheet_small.xml',
        'data/balance_sheet_micro.xml',
        'data/account_report_ec_sales_list_report.xml',
        'data/account_report_vat_eu.xml',
        'data/vat_eu_export_template.xml',
        'data/jpk_fa_export_template.xml',
        'data/jpk_fa.xml',
        'views/jpk_fa_report_views.xml',
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'website': 'https://www.odoo.com/app/accounting',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
