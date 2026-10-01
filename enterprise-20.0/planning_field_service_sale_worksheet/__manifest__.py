# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Field Service Reports - Sale',
    'category': 'Services/Field Service',
    'summary': 'Create Reports for Field service technicians',
    'depends': ['planning_field_service_sale_timesheet', 'planning_field_service_worksheet'],
    'data': [
        'views/product_template_views.xml',
    ],
    'demo': [
        'data/product_product_demo.xml',
    ],
    'auto_install': True,
    'post_init_hook': 'post_init',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
