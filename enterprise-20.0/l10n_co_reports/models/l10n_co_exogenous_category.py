# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

EXOGENOUS_REPORT_TYPES = [
    ('1001', '1001'),
    ('1003', '1003'),
    ('1005', '1005'),
    ('1006', '1006'),
    ('1007', '1007'),
    ('1008', '1008'),
    ('1009', '1009'),
]


class L10n_CoExogenousCategory(models.Model):
    _name = 'l10n_co.exogenous.category'
    _description = 'Colombian Exogenous Category'
    _order = 'sequence'

    name = fields.Char(string="Name", required=True, translate=True)
    sequence = fields.Integer(string="Sequence", required=True)
    report_type = fields.Selection(
        string="Applicable Report",
        required=True,
        selection=EXOGENOUS_REPORT_TYPES,
    )

    _name_uniq = models.Constraint(
        'unique(name, report_type)',
        'An exogenous category with the same name and report already exists.',
    )
