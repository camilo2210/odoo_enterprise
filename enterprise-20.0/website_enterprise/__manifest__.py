# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Website Enterprise',
    'category': 'Website/Website',
    'summary': 'Get the enterprise look and feel',
    'description': """
This module overrides community website features and introduces enterprise look and feel.
    """,
    'depends': ['web_enterprise', 'website'],
    'data': [
        'data/website_data.xml',
        'views/snippets/snippets.xml',
        'views/website_enterprise_templates.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'website_enterprise/static/src/client_actions/*/*',
        ],
        'website.assets_editor': [
            'website_enterprise/static/src/js/systray_items/*.js',
            'website_enterprise/static/src/components/navbar/*',
            'website_enterprise/static/src/systray_items/*',
        ],
    }
}
