# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Rental/Planning Bridge",
    'summary': """This module Integrate Planning with Rental""",
    'category': 'Sales/Sales',
    'depends': ['sale_planning', 'sale_renting'],
    'auto_install': True,
    'data': [
        'views/planning_role_views.xml',
        'views/planning_slot_views.xml',
        'views/sale_order_views.xml',
    ],
    'demo': ['data/demo.xml'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'sale_renting_planning/static/src/**/*',
        ],
    },
    'uninstall_hook': 'uninstall_hook',
}
