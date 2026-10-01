from odoo import fields, models


class AvataxParameterSelection(models.Model):
    _name = 'avatax.parameter.selection'
    _description = "Avatax Parameter Selection"

    name = fields.Char(required=True, readonly=True)
    parameter_id = fields.Many2one('avatax.parameter', required=True, index=True, ondelete='cascade', readonly=True)

    _name_parameter_uniq = models.Constraint(
        'UNIQUE (name, parameter_id)',
        "The selection value already exists for this parameter.",
    )
