# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Sign AI Integration",
    'category': 'Hidden',
    'summary': "Sign AI integration",
    'depends': ['sign', 'ai'],
    'data': [
        'wizard/sign_send_request_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sign_ai/static/src/sign_ai_button.js',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
