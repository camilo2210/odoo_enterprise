from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('name')
    def _onchange_name_predictive(self):
        if not self.purchase_line_id:
            super()._onchange_name_predictive()
