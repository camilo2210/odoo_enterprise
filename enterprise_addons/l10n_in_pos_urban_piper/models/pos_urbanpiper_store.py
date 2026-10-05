# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosUrbanPiperStore(models.Model):
    _inherit = 'pos.urbanpiper.store'

    def _default_tax_type(self):
        if self.env.company.country_code == 'IN':
            return 'total_excluded'
        return super()._default_tax_type()
