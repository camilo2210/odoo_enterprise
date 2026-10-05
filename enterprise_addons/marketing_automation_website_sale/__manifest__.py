{
    'name': "E-Commerce Marketing Automation",
    'summary': "Marketing Automation Templates for E-Commerce",
    'category': "Marketing/Marketing Automation",
    'depends': [
        'marketing_automation',
        'website_sale',
    ],
    'data': [
        'views/mailing_arch_templates.xml',
        'views/marketing_campaign_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'marketing_automation_website_sale/static/src/components/**/*'
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
