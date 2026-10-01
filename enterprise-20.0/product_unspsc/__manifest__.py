# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'UNSPSC product codes',
    'version': '0.4',
    'category': 'Accounting/Accounting',
    'summary': 'UNSPSC product codes',
    'description': """
Countries like Colombia, Peru, Mexico, Denmark need to be able to use the
UNSPSC code for their products and uoms.
    """,
    'depends': ['account'],
    'data': ['views/product_views.xml', 'security/ir.access.csv'],
    "post_init_hook": "post_init_hook",
    'uninstall_hook': 'uninstall_hook',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'other_files': [
        # files loaded from hooks
        'data/product_data.xml',
        'data/product.unspsc.code.csv',
        'demo/product_demo.xml',
    ],
}
