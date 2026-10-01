# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "PoS - Planning",
    'category': "Sales/Point of Sale",
    'summary': 'Link module between Point of Sale and Planning',
    'description': """
This module allows employees to log in to the Point of Sale based on their scheduled shifts in the Planning module (date and time slots).
    """,
    'depends': ['pos_hr', 'planning'],
    'data': [
        'views/planning_role_views.xml',
    ],
    'demo': [
        'demo/pos_planning_demo.xml',
    ],
    'auto_install': True,
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_planning/static/src/**/*',
        ],
        'web.assets_tests': [
            'pos_planning/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'pos_planning/static/tests/unit/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
