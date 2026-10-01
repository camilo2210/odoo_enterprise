{
    'name': 'Field Service - Sale - Timesheet',
    'summary': 'Plan intervention and invoice your time and materials to your customers',
    'category': 'Human Resources/Planning',
    'author': 'Odoo S.A.',
    'maintainer': 'Odoo S.A.',
    'website': 'https://www.odoo.com/app/planning',
    'license': 'OEEL-1',
    'depends': [
        'planning_field_service',
        'sale_timesheet_enterprise',
        'sale_planning',
    ],
    'data': [
        'data/project_task_type_data.xml',
        'data/project_project_data.xml',
        'data/planning_role_data.xml',
        'data/product_product_data.xml',
        'data/res_config_settings_data.xml',
        'views/account_analytic_line_views.xml',
        'views/hr_employee_views.xml',
        'views/planning_slot_views.xml',
        'views/product_product_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/planning_slot_portal_templates.xml',
        'views/planning_templates.xml',
        'views/res_config_settings_views.xml',
        'report/worksheet_custom_report_templates.xml',
        'views/planning_field_service_sale_timesheet_menus.xml'
    ],
    'demo': [
        'data/hr_employee_demo.xml',
        'data/product_product_demo.xml',
        'data/project_task_type_demo.xml',
        'data/project_project_demo.xml',
        'data/res_users_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'planning_field_service_sale_timesheet/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'planning_field_service_sale_timesheet/static/tests/**/*',
        ]
    },
    'post_init_hook': 'post_init',
    'uninstall_hook': 'uninstall_hook',
    'auto_install': ['sale_planning', 'planning_field_service'],
}
