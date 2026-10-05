{
    'name': 'ESG HR',
    'summary': "Use your employee data to measure important ESG metrics (e.g. employee commuting, sex parity).",
    'depends': [
        'esg',
        'hr',
    ],
    'data': [
        'data/esg_hr_report_template_data.xml',
        'report/esg_employee_report_views.xml',
        'views/esg_menus.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'esg_hr/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
