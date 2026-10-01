from odoo import models

from odoo.addons.voip.models.res_users_settings import E164_NUMBER_RE


class ResUsers(models.Model):
    _inherit = "res.users"

    def _voip_disconnected_forward_number(self):
        number = self._phone_format(fname="mobile_phone")
        if number and E164_NUMBER_RE.fullmatch(number):
            return number
        return super()._voip_disconnected_forward_number()
