# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "CRM enterprise",
    'category': "Sales/CRM",
    'summary': "Advanced features for CRM",
    'description': """
Contains advanced features for CRM such as new views and scanning
business cards to generate new leads from them
    """,
    'depends': ['crm', 'web_cohort', 'web_map'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'auto_install': ['crm'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'crm_enterprise/static/src/**/*',
            ('remove', 'crm_enterprise/static/src/views/**'),
        ],
        'web.assets_backend_lazy': [
            'crm_enterprise/static/src/views/**',
        ],
        'web.assets_unit_tests': [
            'crm_enterprise/static/tests/**/*',
        ],
    }
}
