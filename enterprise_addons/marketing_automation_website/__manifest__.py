{
    'name': "Website Marketing Automation",
    'summary': "Marketing Automation Overrides for Website",
    'category': "Marketing/Marketing Automation",
    'depends': [
        'marketing_automation',
        'website',
    ],
    'data': [
        'views/marketing_campaign_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'marketing_automation_website/static/src/components/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
