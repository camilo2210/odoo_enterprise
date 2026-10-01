# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class PosUrbanPiperStore(models.Model):
    _inherit = 'pos.urbanpiper.store'

    def _pos_config_domain(self):
        """Extend the domain to exclude kiosk-mode configs when self-order is installed."""
        domain = super()._pos_config_domain()
        return Domain.AND([domain, Domain('self_ordering_mode', '!=', 'kiosk')])
