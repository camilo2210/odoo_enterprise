# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class SignItemRole(models.Model):
    _inherit = "sign.item.role"

    auth_method = fields.Selection(
        selection_add=[
            ('emsigner', 'Via Aadhar eSign'),
        ],
        ondelete={'emsigner': 'cascade'}
    )

    @api.constrains('auth_method')
    def _check_auth_method_availability(self):
        for role in self:
            if role.auth_method == 'emsigner' and self.env.company.country_code != 'IN':
                raise UserError(self.env._("Aadhaar sign authentication is available only for companies in India."))

    @api.model
    def _get_auth_method_iap_mapping(self):
        iap_map = super()._get_auth_method_iap_mapping()
        iap_map.update(emsigner='emsigner_proxy')
        return iap_map
