# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Repair',
    'summary':  'Allow user without repair right to access field serivce stock.picking',
    'description': "Allow user without repair right to access field service stock.picking",
    'category': 'Services/Field Service',
    'depends': ['planning_field_service_sale_stock', 'repair'],
    'data': [
        'security/ir.access.csv',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
