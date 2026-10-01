# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Point of Sale Settle Due',
    'category': 'Point of Sale',
    'sequence': 6,
    'summary': "Settle partner's due in the POS UI.",
    'depends': ['point_of_sale', 'account_followup'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'data': [
        'views/account_move_views.xml',
    ],
    'assets': {
        'web.assets_unit_tests': [
            'pos_settle_due/static/tests/unit/**/*',
        ],
        'point_of_sale._assets_pos': [
            'pos_settle_due/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_settle_due/static/tests/tours/**/*'
        ],
    }
}
