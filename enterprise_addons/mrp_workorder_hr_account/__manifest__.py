# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Employees cost registration on production",
    'category': "Supply Chain/Manufacturing",
    'summary': 'Analytic cost of employee work in manufacturing',

    'description': """ """,

    'depends': ['mrp_workorder', 'mrp_account_enterprise'],
    'data': ['report/mrp_report_views.xml'],

    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'other_files': [
        'report/mrp_report_views.xml',
    ],
}
