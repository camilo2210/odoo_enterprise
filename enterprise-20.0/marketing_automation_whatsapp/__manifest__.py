{
    'name': "WhatsApp in Marketing Automation",
    'summary': "Integrate WhatsApp in marketing campaigns",
    'category': "Marketing/Marketing Automation",
    'depends': [
        'marketing_automation',
        'whatsapp',
    ],
    'data': [
        'views/marketing_activity_views.xml',
        'views/whatsapp_template_views.xml',
        'views/marketing_campaign_views.xml',
        'security/marketing_automation_whatsapp_security.xml',
    ],
    'assets': {
        'web.assets_backend': [
            "marketing_automation_whatsapp/static/**/*",
        ]
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
