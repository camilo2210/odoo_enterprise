# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Shiprocket Shipping",
    'description': "Send your parcels through shiprocket and track them online",
    'category': 'Shipping Connectors',
    'sequence': 317,
    'application': True,
    'depends': ['stock_delivery', 'mail'],
    'data': [
        'data/data.xml',
        'views/delivery_carrier_views.xml',
        'views/stock_picking.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
