# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI HR Recruitment Integration Website Livechat',
    'category': 'Hidden',
    'summary': "AI HR Recruitment Integration Website preview cards for website livechat",
    'depends': ['ai_website_livechat', 'website_hr_recruitment'],
    'assets': {
        'web.assets_frontend': [
            'ai_hr_recruitment_integration_website_livechat/static/src/scss/ai_hr_job_preview.scss',
        ],
    },
    'author': 'Odoo S.A.',
    'auto_install': True,
    'license': 'OEEL-1',
}
