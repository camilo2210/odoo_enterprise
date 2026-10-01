# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Timer',
    'sequence': 24,
    'summary': 'Record time',
    'category': 'Services/Timesheets',
    'description': """
This module implements a timer.
==========================================

It adds a timer to a view for time recording purpose
    """,
    'depends': ['web', 'mail'],
    'data': [
        'security/ir.access.csv',
        ],
    'assets': {
        'web.assets_backend': [
            'timer/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'timer/static/tests/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
