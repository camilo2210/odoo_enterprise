# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _get_deferred_lines_values(self, account_id, balance, ref, analytic_distribution, line=None):
        deferred_lines_values = super()._get_deferred_lines_values(account_id, balance, ref, analytic_distribution, line)
        return {
            **deferred_lines_values,
            'vehicle_id': int(line['vehicle_id'] or 0) or None,
        }

    @api.model
    def _get_deferred_amounts_by_line_values(self, line):
        values = super()._get_deferred_amounts_by_line_values(line)
        values['vehicle_id'] = int(line['vehicle_id'] or 0) or None
        return values
