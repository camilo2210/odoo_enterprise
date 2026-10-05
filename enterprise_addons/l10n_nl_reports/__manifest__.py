# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Netherlands - Accounting Reports',
    'version': '1.5',
    'category': 'Accounting/Localizations/Reporting',
    'description': """
Accounting reports for Netherlands
Submit your Tax Reports to the Dutch tax authorities
    """,
    'author': 'Odoo S.A.',
    'depends': ['l10n_nl', 'account_reports', 'certificate'],
    'external_dependencies': {
        'python': ['xmlsec'],
        'apt': {
            'xmlsec': 'python3-xmlsec',
        },
    },
    'data': [
        'data/account_financial_report_profit_loss.xml',
        'data/account_financial_report_profit_loss_tags.xml',
        'data/account_financial_report_balance_sheet.xml',
        'data/account_financial_report_balance_sheet_tags.xml',
        'data/account_report_ec_sales_list_report.xml',
        'data/account_return_data.xml',
        'data/cron.xml',
        'data/ir_config_parameter.xml',
        'data/mail_templates.xml',
        'data/tax_report.xml',
        'data/xml_audit_file_3_2.xml',
        'report/l10n_nl_sbr_icp_template.xml',
        'report/sbr_tax_report_templates.xml',
        'views/account_return_views.xml',
        'views/res_config_settings_view.xml',
        'wizard/l10n_nl_sbr_icp_wizard_view.xml',
        'wizard/l10n_tax_report_sbr_views.xml',
        'wizard/vat_pay_wizard.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_nl_reports/static/src/scss/account_return.scss',
        ],
    },
    'demo': [
        'demo/ir_config_parameter.xml',
    ],
    'auto_install': ['l10n_nl', 'account_reports'],
    'license': 'OEEL-1',
}
