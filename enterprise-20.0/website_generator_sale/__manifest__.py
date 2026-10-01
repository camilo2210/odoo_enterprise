# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Website Generator Sale',
    'category': 'Website/Website',
    'summary': 'Import products from a pre-existing website',
    'description': """
        Extension of the Website Generator.
        Generate products in Odoo based on the products found on the external website.
    """,
    'depends': ['website_generator', 'website_sale'],
    'data': [
        'templates/shop_page_templates.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'website_generator/static/src/client_actions/import_website_cog_menu/*',
            'website_generator_sale/static/src/client_actions/cog_menu_import_btn_sale/*',
            'website_generator/static/src/client_actions/import_form_dialog/*',
        ],
        'web.assets_frontend': [
            'website_generator_sale/static/src/interactions/*',
            'website_generator/static/src/client_actions/import_form_dialog/*',
            'website_generator/static/src/client_actions/import_form/*',
        ],
    },
}
