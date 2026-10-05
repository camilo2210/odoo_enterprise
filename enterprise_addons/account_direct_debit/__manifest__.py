{
    'name': 'Direct Debit Mandate',
    'author': 'Odoo S.A.',
    'category': 'Hidden',
    'summary': 'Manage Direct Debit Mandates',
    'description': """
This module provides the base model and logic for managing Direct Debit Mandates.
The module is not meant to use as a standalone module, only through its dependent modules.
    """,
    'depends': ['account_batch_payment'],
    'data': [
        'security/ir.access.csv',
        'data/account_direct_debit_mandate.xml',
        'data/ir_cron.xml',
        'report/account_direct_debit_mandate_report.xml',
        'report/report_invoice.xml',
        'views/account_direct_debit_mandate_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_view.xml',
        'views/res_partner_views.xml',
        'wizard/account_mandate_send_views.xml',
    ],
    'license': 'OEEL-1',
}
