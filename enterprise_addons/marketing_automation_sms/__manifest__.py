# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "SMS Marketing in Marketing Automation",
    'summary': "Integrate SMS Marketing in marketing campaigns",
    'category': "Marketing/Marketing Automation",
    'depends': [
        'marketing_automation',
        'mass_mailing_sms'
    ],
    'data': [
        'views/mailing_mailing_views.xml',
        'views/mailing_trace_views.xml',
        'views/marketing_activity_views.xml',
        'views/marketing_campaign_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            "marketing_automation_sms/static/**/*",
        ]
    },
    'uninstall_hook': '_uninstall_hook',
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
