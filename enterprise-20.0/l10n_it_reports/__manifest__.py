# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Italy - Accounting Reports',
    'description': """
Accounting reports for Italy
============================

    """,
    'category': 'Accounting/Accounting',
    'depends': ['l10n_it', 'account_reports'],
    'data': [
        'data/account_profit_and_loss_data.xml',
        'data/account_balance_sheet_report_data.xml',
        'data/account_reduce_balance_sheet_report_data.xml',
        'data/account_report_ec_sales_list_report.xml',
        'data/account_return_data.xml',
        'data/account_libro_giornale_list_report.xml',
        'data/xml_export/tax_monthly_report_vat.xml',
        'data/xml_export/tax_report_export_template.xml',
        'views/account_return_views.xml',
        'views/journal_report_templates.xml',
        'wizard/monthly_tax_report_xml_export_view.xml',
        'security/ir.access.csv',
    ],
    'auto_install': ['l10n_it', 'account_reports'],
    'author': 'Odoo S.A.',
    'assets': {
        'account_reports.assets_pdf_export': [
            'l10n_it_reports/static/src/scss/pdf_export_template.scss',
        ],
    },
    'license': 'OEEL-1',
}
