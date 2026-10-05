{
    'name': 'Sale Project Enterprise',
    'category': 'Sales/Sales',
    'depends': ['sale_project', 'project_enterprise', 'analytic_enterprise'],
    'data': [
        'views/account_analytic_line_views.xml'
    ],
    'auto_install': ['sale_project'],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend_lazy': [
            'sale_project_enterprise/static/src/**/*',
        ],
    },
}
