from odoo import fields, models


class AvataxParameter(models.Model):
    _name = 'avatax.parameter'
    _description = "Avatax Parameter"

    name = fields.Char(required=True)
    technical_name = fields.Char(required=True)
    description = fields.Text()
    # Only 'Product' is currently synced and supported. Support for other scopes
    # can be added later, at which point we add selections to this field.
    scope = fields.Selection(
        selection=[
            ('Product', 'Product'),
        ],
        required=True,
    )
    data_type = fields.Selection(
        selection=[
            ('Boolean', 'Boolean'),
            ('NumericMeasured', 'Numeric Measured'),
            ('String', 'String'),
            ('Enumeration', 'Enumeration'),
            ('NumericCurrency', 'Numeric Currency'),
            ('Date', 'Date'),
        ],
        required=True,
    )
    measurement_type = fields.Char()
    selection_ids = fields.One2many('avatax.parameter.selection', 'parameter_id')
    company_id = fields.Many2one('res.company', required=True)

    _technical_name_company_uniq = models.Constraint(
        'UNIQUE (technical_name, company_id)',
        "The parameter already exists for this company.",
    )
