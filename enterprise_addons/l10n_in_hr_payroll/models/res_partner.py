# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_address_lines(self):
        self.ensure_one()
        return [
            self.street or 'NA',
            self.street2 or '',
            self.city or '',
            self.state_id.name if self.state_id else '',
            self.country_id.name if self.country_id else '',
        ]
