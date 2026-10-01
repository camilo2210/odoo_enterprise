# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Website Appointment Livechat',
    'category': 'Hidden',
    'summary': "AI Website Appointment preview cards for website livechat",
    'depends': ['ai_website_livechat', 'website_appointment'],
    'assets': {
        'web.assets_frontend': [
            'ai_website_appointment_livechat/static/src/scss/ai_appointment_preview.scss',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
