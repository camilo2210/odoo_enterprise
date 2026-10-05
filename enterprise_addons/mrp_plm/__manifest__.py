# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Product Lifecycle Management (PLM)',
    'category': 'Supply Chain/Product Lifecycle Management (PLM)',
    'sequence': 155,
    'summary': """Manage engineering change orders on products, bills of material""",
    'website': 'https://www.odoo.com/app/plm',
    'depends': ['mrp'],
    'description': """
Product Life Management
=======================

* Versioning of Bill of Materials and Products
* Different approval flows possible depending on the type of change order

""",
    'data': [
        'security/mrp_plm.xml',
        'data/mrp_data.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_document_views.xml',
        'views/mrp_eco_views.xml',
        'views/product_views.xml',
        'views/mrp_production_views.xml',
        'wizard/mrp_eco_update_product_version_views.xml',
        'report/mrp_report_bom_structure.xml',
        'report/mrp_eco_changes_report.xml',
        'security/ir.access.csv',
    ],
    'demo': [
        'data/mrp_demo.xml',
    ],
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'mrp_plm/static/src/**/*.js',
            'mrp_plm/static/src/**/*.scss',
            'mrp_plm/static/src/**/*.xml',
        ],
        'web.report_assets_common': [
            'mrp_plm/static/src/scss/mrp_eco_changes_report.scss',
        ],
    }
}
