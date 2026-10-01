# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Accounting - MRP',
    'category': 'Supply Chain/Manufacturing',
    'summary': 'Analytic accounting in Manufacturing',
    'description': """
Analytic Accounting in MRP
==========================

* Cost structure report
""",
    'website': 'https://www.odoo.com/app/manufacturing',
    'depends': ['mrp_account'],
    'data': [
        'views/mrp_account_view.xml',
        'reports/mrp_report_views.xml',
        'security/ir.access.csv',
        ],
    'demo': ['demo/mrp_account_demo.xml'],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.report_assets_common': [
            'mrp_account_enterprise/static/src/scss/cost_structure_report.scss',
        ],
    }
}
