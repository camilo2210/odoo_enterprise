{
    'name': 'Slovakia - Accounting Reports',
    'icon': '/account/static/description/l10n.png',
    'description': """
Accounting reports for Slovakia
=====================================
This module includes accounting reports for Slovakia, including:
- Balance Sheet + Profit and Loss (XML export)
- Tax report (XML export). For more information, see https://www.financnasprava.sk/sk/podnikatelia/dane/dan-z-pridanej-hodnoty/danove-priznanie
- VAT Control Statement (creation and XML export). For more information, see https://www.financnasprava.sk/sk/podnikatelia/dane/dan-z-pridanej-hodnoty/kontrolny-vykaz-dph
- VIES Summary Statement (creation and XML export). For more information, see https://www.financnasprava.sk/sk/podnikatelia/dane/dan-z-pridanej-hodnoty/suhrnny-vykaz-dph
    """,
    'category': 'Accounting/Localizations/Reporting',
    'depends': ['l10n_sk', 'account_reports'],
    'data': [
        'data/annual_statements_menuitem.xml',
        'data/balance_sheet.xml',
        'data/profit_loss.xml',
        'data/annual_statements.xml',
        'data/annual_statements_export.xml',
        'data/tax_report.xml',
        'data/tax_report_export.xml',
        'data/account_account_tag_data.xml',
        'data/control_statement_report.xml',
        'data/control_statement_report_export.xml',
        'data/vies_summary_report_export.xml',
        'data/vies_summary_report.xml',
        'data/uom.uom.csv',
        'data/account_return_data.xml',
        'views/account_move_views.xml',
        'views/product_views.xml',
        'views/res_company_views.xml',
        'views/uom_uom_views.xml',
        'wizard/l10n_sk_generate_annual_statements_report.xml',
        'wizard/vat_control_statement_wizard.xml',
        'wizard/vat_return_submission_wizard.xml',
        'wizard/vies_summary_submission_wizard.xml',
        'security/ir.access.csv',
    ],
    'demo': ['demo/demo_company.xml'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
