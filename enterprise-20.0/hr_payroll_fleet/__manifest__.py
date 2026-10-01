# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payroll - Fleet',
    'category': 'Human Resources/Payroll',
    'summary': 'Integration between Payroll and Fleet.',
    'depends': ['hr_payroll', 'hr_fleet'],
    'auto_install': True,
    'data': [
        'data/hr_payroll_warning_data.xml',
        'views/fleet_vehicle_model_views.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
