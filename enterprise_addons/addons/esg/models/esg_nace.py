from odoo import api, fields, models


class EsgNace(models.Model):
    _name = 'esg.nace'
    _description = 'NACE'
    _rec_name = 'complete_name'

    name = fields.Char(required=True)
    complete_name = fields.Char(compute='_compute_complete_name', search='_search_complete_name')
    code = fields.Char(required=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The code of a NACE must be unique.',
    )

    @api.depends('code', 'name')
    def _compute_complete_name(self):
        for nace in self:
            nace.complete_name = f'{nace.code} - {nace.name}'

    def _search_complete_name(self, operator, value):
        if operator not in ('ilike', 'like', '=', '=ilike'):
            raise NotImplementedError(f'Operator {operator} not supported')
        return ['|', ('code', operator, value), ('name', operator, value)]
