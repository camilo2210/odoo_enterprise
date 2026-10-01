# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'POS UrbanPiper - India',
    'category': 'Sales/Point of Sale',
    'description': """
This module integrates with UrbanPiper to receive and manage orders from Swiggy and Zomato (Food delivery providers for India).
    """,
    'depends': ['l10n_in', 'pos_urban_piper'],
    'data': [
        'views/pos_urbanpiper_store_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
