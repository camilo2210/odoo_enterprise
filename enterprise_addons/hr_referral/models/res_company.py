# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import BinaryBytes, file_open


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_default_referral_background(self):
        with file_open('hr_referral/static/src/img/bg.svg', 'rb') as f:
            return BinaryBytes(f.read())

    hr_referral_background = fields.Image(string='Referral Background', default=_get_default_referral_background, required=True)

    def write(self, vals):
        if 'hr_referral_background' in vals:
            self.env["ir.config_parameter"].sudo().set_bool('hr_referral.show_grass', not vals['hr_referral_background'])
            if not vals['hr_referral_background']:
                vals['hr_referral_background'] = self._get_default_referral_background()
        return super().write(vals)

    def _init_default_background(self):
        if not self:
            return
        self.hr_referral_background = self._get_default_referral_background()
        self.env["ir.config_parameter"].sudo().set_bool('hr_referral.show_grass', True)
