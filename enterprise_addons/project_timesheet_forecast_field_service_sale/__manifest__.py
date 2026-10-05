{
    'name': 'Project Forecast - Field Service - Sale',
    'summary': 'Add project and task to your interventions',
    'category': 'Human Resources/Planning',
    'author': 'Odoo S.A.',
    'maintainer': 'Odoo S.A.',
    'website': 'https://www.odoo.com/app/planning',
    'license': 'OEEL-1',
    'depends': [
        'project_timesheet_forecast_sale',
        'planning_field_service_sale_timesheet',
    ],
    'data': [
        'views/planning_slot_views.xml',
        'views/project_task_views.xml',
        'views/res_config_settings_views.xml',
        'report/planning_analysis_report_views.xml',
    ],
    'demo': [
        'data/project_task_demo.xml',
        'data/planning_slot_demo.xml',
    ],
    'auto_install': True,
}
