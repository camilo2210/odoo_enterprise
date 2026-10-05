# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Fiscal Categories on Fleets',
    'category': 'Accounting/Accounting',
    'summary': 'Manage fiscal categories with fleets',
    'depends': ['account_accountant_fleet', 'account_fiscal_categories'],
    'data': [
        'data/account_fiscal_report.xml',
        'views/fleet_vehicle_views.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'account_fiscal_categories_fleet/static/src/components/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
