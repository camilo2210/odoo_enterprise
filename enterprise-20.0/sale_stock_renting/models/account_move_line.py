# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _use_inventory_valuation(self):
        self.ensure_one()
        return super()._use_inventory_valuation() and not any(
            sol.is_rental for sol in self.sale_line_ids
        )
