# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Website Generator Blog',
    'category': 'Website/Website',
    'summary': 'Import blogs from a pre-existing website',
    'description': """
        Extension of the Website Generator.
        Generate blogs in Odoo based on the products found on the external website.
    """,
    'depends': ['website_generator', 'website_blog'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'website_generator/static/src/client_actions/import_website_cog_menu/*',
            'website_generator_blog/static/src/client_actions/import_website_cog_menu_blog/*',
            'website_generator/static/src/client_actions/import_form_dialog/*',
        ],
    },
}
