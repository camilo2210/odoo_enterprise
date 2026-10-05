# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "AI Website Helpdesk",
    'category': 'Hidden',
    'summary': "AI website helpdesk",
    'depends': ['ai_website_livechat', 'website_helpdesk_forum'],
    'data': [
        'views/helpdesk_templates.xml',
    ],
    'assets': {
        'web.assets_tests': [
            'ai_website_helpdesk/static/tests/tours/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
