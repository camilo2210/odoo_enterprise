# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Brazilian Accounting EDI",
    "description": """
Brazilian Accounting EDI
========================
Provides electronic invoicing for Brazil through Avatax.
""",
    "category": "Accounting/Localizations/EDI",
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "depends": ["l10n_br_avatax"],
    "data": [
        "data/mail_template_data.xml",
        "data/ir_cron.xml",
        "data/l10n_br.customs.regime.csv",
        "data/l10n_br.nbs.code.csv",
        "data/l10n_br_operation_type_data.xml",
        "views/account_move_view.xml",
        "views/report_invoice.xml",
        "views/account_portal_views.xml",
        "views/payment_method_views.xml",
        "views/l10n_br_operation_type_views.xml",
        "views/l10n_br_nbs_code_views.xml",
        "views/l10n_br_customs_regime_views.xml",
        "views/l10n_br_ncm_code_views.xml",
        "views/product_template_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "wizard/l10n_br_edi_invoice_update_views.xml",
        "wizard/l10n_br_edi_cancel_range_views.xml",
        'security/ir.access.csv',
    ],
    "demo": [
        "data/res_partner_demo.xml",
        "data/uom_uom_demo.xml",
        "data/product_product_demo.xml",
    ],
    "post_init_hook": "_l10n_br_res_company_post_init",
}
