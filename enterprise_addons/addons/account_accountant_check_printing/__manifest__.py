# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Account accountant check printing',
    'category': 'Accounting',
    'summary': 'Allows using Reconciliation with the account check printing.',
    'depends': ['account_accountant', 'account_check_printing'],
    'data': [
        'views/bank_rec_widget_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
