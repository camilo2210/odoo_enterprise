# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _get_order_for_session_closing(self):
        """ We filter the order that are paid with a resource-linked payment method and are thus
        linked to a sale_order through sale_order_id because the do not want to create journal entries
        for those orders. Indeed, the accounting entries for those orders are created
        by the sale order accounting mechanism.
        """
        return super()._get_order_for_session_closing().filtered(lambda o: not o.sale_order_id)
