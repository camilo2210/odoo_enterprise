# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

    @api.depends('account_move_line_id.price_subtotal',
        'account_move_line_id.non_deductible_tax_value')
    def _compute_amount(self):
        for log_service in self:
            if not log_service.account_move_line_id:
                continue
            account_move_line_id = log_service.account_move_line_id
            log_service.amount = account_move_line_id.currency_id.round(account_move_line_id.debit + account_move_line_id.non_deductible_tax_value)
