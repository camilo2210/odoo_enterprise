{
    'name': 'Website Planning Field Service',
    'category': 'Human Resources/Planning',
    'summary': 'Collect intervention requests via an online form',
    'depends': ['planning_field_service', 'website'],
    'data': [
        'data/planning_slot_data.xml',
        'data/website_menu_data.xml',
        'views/planning_slot_views.xml',
        'views/website_planning_field_service_templates.xml',
        'views/website_planning_field_service_menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_planning_field_service/static/src/interactions/service_requests_form.js',
            'website_planning_field_service/static/src/snippets/s_website_form/form_patch.js',
        ],
        'website.website_builder_assets': [
            'website_planning_field_service/static/src/js/website_planning_field_service_editor.js',
        ],
        'website.assets_inside_builder_iframe': [
            'website_planning_field_service/static/src/js/website_planning_field_service_editor.edit.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'uninstall_hook': 'uninstall_hook',
    'auto_install': True,
}
