from odoo import api, fields, models


class EsgESRS(models.Model):
    _name = 'esg.esrs'
    _description = 'ESRS'
    _order = 'category, code, id'
    _rec_name = 'complete_name'

    name = fields.Char(required=True)
    complete_name = fields.Char(compute='_compute_complete_name', search='_search_complete_name')
    code = fields.Char(required=True)
    section = fields.Char(required=True)
    dr = fields.Char(string='Disclosure Requirement', required=True)
    category = fields.Selection([
        ('1_environment', 'Environment'),
        ('2_social', 'Social'),
        ('3_governance', 'Governance'),
    ], required=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'The code of an ESRS must be unique.',
    )

    @api.depends('code', 'name')
    def _compute_complete_name(self):
        for esrs in self:
            esrs.complete_name = f'{esrs.code} {esrs.name}'

    def _search_complete_name(self, operator, value):
        if operator not in ('ilike', 'like', '=', '=ilike'):
            raise NotImplementedError(f'Operator {operator} not supported')
        return ['|', ('code', operator, value), ('name', operator, value)]
