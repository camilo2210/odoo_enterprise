# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale Sale Renting Planning',
    'category': 'Point of Sale',
    'sequence': 15,
    'summary': "Link between PoS Sale planning and Sale Renting Planning.",
    'depends': ['pos_sale_planning', 'sale_renting_planning'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_sale_renting_planning/static/src/**/*',
        ],
    },
}
