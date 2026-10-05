from odoo import fields, models


class EsgEmissionFactor(models.Model):
    _inherit = 'esg.emission.factor'

    currency_name = fields.Char(string="Currency Name", related='currency_id.name')
    uom_name = fields.Char(string="UoM Name", related='uom_id.name')
    company_name = fields.Char(string="Company Name", related='company_id.name')
