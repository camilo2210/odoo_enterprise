# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Frontdesk Partnership',
    'category': 'Human Resources/Frontdesk',
    'sequence': 60,
    'description': 'Use grades to filter the validity at a frontdesk',
    'summary': 'Use grades to filter the validity at a frontdesk',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'depends': [
        'frontdesk',
        'barcodes',
        'partnership',
    ],
    'auto_install': ['frontdesk', 'partnership'],
    'data': [
        'views/frontdesk_frontdesk_views.xml',
        'views/frontdesk_templates.xml',
    ],
    'demo': [
        'demo/frontdesk_demo.xml',
    ],
    'assets': {
        'frontdesk_partnership.assets_frontdesk_partnership': [
            ("include", "frontdesk.assets_frontdesk"),
            'frontdesk_partnership/static/src/**/*',
            'barcodes/static/src/**/*',
        ],
    },
}
