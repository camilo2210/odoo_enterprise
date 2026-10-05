from odoo import api, models
from odoo.exceptions import ValidationError


class EsgEmissionFactor(models.Model):
    _inherit = "esg.emission.factor"

    @api.ondelete(at_uninstall=False)
    def _prevent_unlinking_commuting_factor(self):
        for factor in self:
            if factor == self.env.ref("esg_hr_fleet.employee_commuting_factor"):
                raise ValidationError(self.env._(
                    "The “%(name)s” Emission Factor is required by the ESG app and cannot be deleted.",
                    name=factor.name,
                ))
