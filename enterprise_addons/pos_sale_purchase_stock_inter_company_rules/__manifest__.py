# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Inter Company Module for Pos & Sale/Purchase Orders (with Inventory link)',
    'summary': 'Intercompany SO/PO with Pos',
    'category': 'Productivity',
    'description': ''' Module for synchronization of Inventory Documents between several companies.
    For example, this allows you to have a delivery receipt created automatically in the receiving company when another company of the system confirms a delivery order.
''',
    'depends': [
        'pos_sale',
        'sale_purchase_stock_inter_company_rules'
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
