# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'EDI for Mexico',
    'version': '0.3',
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Mexican Localization for EDI documents',
    'description': """
EDI Mexican Localization
========================
Allow the user to generate the EDI document for Mexican invoicing.

This module allows the creation of the EDI documents and the communication with the Mexican certification providers (PACs) to sign/cancel them.
    """,
    'depends': [
        'account_accountant',
        'l10n_mx',
        'product_unspsc',
        'certificate',
    ],
    'data': [

        'data/4.0/cfdi.xml',
        'data/4.0/payment20.xml',
        'data/l10n_mx_edi_payment_method_data.xml',
        'data/ir_cron.xml',
        'data/res_currency_data.xml',
        'data/l10n_mx_uom_unspsc.xml',
        'data/addenda.xml',
        'data/templates/cfdi_request_templates.xml',

        'views/account_journal_view.xml',
        'views/account_move_view.xml',
        'views/account_payment_views.xml',
        'views/account_payment_register_views.xml',
        'views/account_portal_templates.xml',
        'views/account_tax_view.xml',
        'views/certificate_certificate_views.xml',
        'views/l10n_mx_edi_addenda_views.xml',
        'views/bank_rec_widget_views.xml',
        'views/l10n_mx_edi_payment_method_view.xml',
        'views/l10n_mx_edi_document_views.xml',
        'views/report_bank_transaction.xml',
        "views/report_invoice.xml",
        "views/report_payment.xml",
        'views/report_l10n_mx_edi_document.xml',
        'views/res_partner_view.xml',
        'views/res_partner_bank_view.xml',
        'views/res_config_settings_view.xml',
        'views/res_country_view.xml',
        'views/product_views.xml',
        'views/l10n_mx_edi_cfdi_request_views.xml',

        'wizard/l10n_mx_edi_invoice_cancel.xml',
        'wizard/l10n_mx_edi_global_invoice_create.xml',
        'wizard/l10n_mx_edi_register_factoring.xml',
        'wizard/l10n_mx_edi_cfdi_request_wizard_views.xml',

        'data/res_country_data.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'demo/demo_cfdi.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'auto_install': ['l10n_mx'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'l10n_mx_edi/static/src/components/**/*',
        ],
        'web.report_assets_pdf': [
            'l10n_mx_edi/static/src/scss/**/*',
        ],
        'web.report_assets_common': [
            'l10n_mx_edi/static/src/scss/**/*',
        ],
        'web.assets_tests': [
            'l10n_mx_edi/static/tests/tours/**/*',
        ],
    }
}
