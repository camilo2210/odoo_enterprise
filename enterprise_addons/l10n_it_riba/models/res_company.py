from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _name = 'res.company'
    _inherit = 'res.company'

    l10n_it_sia_code = fields.Char(
        string='SIA code',
        help="Identifier used in Italy for interbank transactions"
             " by the Società Interbancaria per l'Automazione"
    )

    @api.constrains('l10n_it_sia_code')
    def _check_l10n_it_sia_code(self):
        if self.filtered(lambda company: company.l10n_it_sia_code and len(company.l10n_it_sia_code) != 5):
            raise ValidationError(_("The SIA code must be exactly 5 characters long."))
