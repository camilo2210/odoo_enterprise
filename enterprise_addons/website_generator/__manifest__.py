# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Website Generator',
    'category': 'Website/Website',
    'summary': 'Import a pre-existing website',
    'description': """
        Generates a new website in Odoo, with the goal of recreating an external website as close as possible.
    """,
    'depends': ['website', 'website_enterprise'],
    'data': [
        'data/cron.xml',
        'views/website_generator_views.xml',
        'views/res_config_settings_views.xml',
        'data/mail_template.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'website_generator/static/src/client_actions/configurator/*',
            'website_generator/static/src/client_actions/generator_wait/*',
            'website_generator/static/src/client_actions/import_form/*',
        ],
        'website.website_builder_assets': [
            'website_generator/static/src/builder/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
