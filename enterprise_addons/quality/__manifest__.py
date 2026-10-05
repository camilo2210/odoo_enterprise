
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Quality Base',
    'category': 'Supply Chain/Quality',
    'sequence': 50,
    'summary': 'Basic Feature for Quality',
    'depends': ['stock'],
    'description': """
Quality Base
===============
* Define quality points that will generate quality checks on pickings,
  manufacturing orders or work orders (quality_mrp)
* Quality alerts can be created independently or related to quality checks
* Possibility to add a measure to the quality check with a min/max tolerance
* Define your stages for the quality alerts
""",
    'data': [
        'security/quality.xml',
        'data/mail_alias_data.xml',
        'data/quality_data.xml',
        'views/quality_views.xml',
        'security/ir.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
