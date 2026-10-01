# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nBeReorganisationMeasure(models.Model):
    _name = 'l10n.be.reorganisation.measure'
    _description = 'BE: Reorganisation Measure'

    name = fields.Char(required=True, translate=True)
    description = fields.Char(required=True, translate=True)
    egov3_code = fields.Char(required=True)
    dmfa_code = fields.Char(required=True)
    color = fields.Integer()

    @api.depends('dmfa_code')
    def _compute_display_name(self):
        for category in self:
            category.display_name = f'[{category.dmfa_code}] {category.name}'

    @api.constrains('egov3_code')
    def _verify_egov3_code(self):
        for measure in self:
            if measure.egov3_code and (len(measure.egov3_code) != 3 or not measure.egov3_code.isdigit()):
                raise ValidationError(_("The eGov-3.0 code must be a sequence of 3 digits."))

    @api.constrains('dmfa_code')
    def _verify_dmfa_code(self):
        for measure in self:
            if measure.dmfa_code and (len(measure.dmfa_code) > 3 or not measure.dmfa_code.isdigit()):
                raise ValidationError(_("The DmfA code must be a sequence of 1 to 3 digits."))
