{
    'name': 'Field Service - Stock',
    'summary': 'Plan intervention and track serial numbers for shifts',
    'category': 'Human Resources/Planning',
    'author': 'Odoo S.A.',
    'maintainer': 'Odoo S.A.',
    'website': 'https://www.odoo.com/app/planning',
    'license': 'OEEL-1',
    'depends': [
        'planning_field_service',
        'stock',
    ],
    'data': [
        'security/ir.access.csv',
        'views/planning_slot_views.xml',
        'views/product_document_views.xml',
        'views/stock_lot_views.xml',
        'report/planning_slots_portal_template.xml',
    ],
    'auto_install': True,
    'post_init_hook': 'post_init',
}
