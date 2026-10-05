# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': '3rd Party Tax Calculation',
    'description': '''
3rd Party Tax Calculation
=========================

Provides a common interface to be used when implementing apps to outsource tax calculation.
    ''',
    'category': 'Accounting/Accounting',
    'depends': ['account', 'payment'],  # payment because of the payment.link.wizard inherit
    'data': [
        'views/account_move_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
