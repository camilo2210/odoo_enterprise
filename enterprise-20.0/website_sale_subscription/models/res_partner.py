from odoo import models
from odoo.fields import Domain
from odoo.addons.sale_subscription.models.sale_order import SUBSCRIPTION_PROGRESS_STATE


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_order_fiscal_position_recompute_domain(self):
        # when changing partner info that impact fiscal position, ensure
        # fiscal position is also up to date on running subscriptions.
        return super()._get_order_fiscal_position_recompute_domain() | Domain([
        '&',
            '|', ('partner_id', 'in', self.ids),
                 ('partner_shipping_id', 'in', self.ids),
            '&', ('website_id', '!=', False),
            '&', ('state', '=', 'sale'),
            '&', ('locked', '=', False),
            '&', ('is_subscription', '=', True),
                 ('subscription_state', 'in', SUBSCRIPTION_PROGRESS_STATE),
        ])
