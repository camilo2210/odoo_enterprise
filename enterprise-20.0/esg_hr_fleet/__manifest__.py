{
    'name': 'ESG HR Fleet',
    'summary': "Measure fleet emissions based on your employees' commuting distance and vehicle data.",
    'depends': [
        'esg',
        'hr_fleet',
    ],
    'data': [
        'data/esg_hr_fleet_data.xml',
        'report/esg_carbon_emission_report_views.xml',
        'report/esg_employee_commuting_report_views.xml',
        'views/esg_menus.xml',
        'views/esg_other_emission_views.xml',
        'views/res_config_settings_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'esg_hr_fleet/static/src/fields/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
