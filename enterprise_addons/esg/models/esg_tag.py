from random import randint

from odoo import fields, models


class EsgTag(models.Model):
    _name = 'esg.tag'
    _description = 'ESG Tags'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer(string='Color', default=_get_default_color)

    _name_uniq = models.Constraint(
        'unique (name)',
        'A tag with the same name already exists.',
    )
