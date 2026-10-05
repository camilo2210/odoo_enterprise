# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale Mobile',
    'category': 'Hidden',
    'summary': 'Odoo Mobile Point of Sale module',
    'description': """
This module provides the point of sale function of the Odoo Mobile App.
        """,
    'depends': [
        'pos_enterprise',
        'web_mobile',
    ],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'web_mobile/static/src/**/*',
            ('remove', 'web_mobile/static/src/webclient/**/*'),
            'pos_mobile/static/src/**/*'
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
