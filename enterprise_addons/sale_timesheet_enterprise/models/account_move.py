# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.fields import Domain
from odoo.addons.sale_timesheet_enterprise.models.sale_order_line import DEFAULT_INVOICED_TIMESHEET


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _analytic_line_domain_get_invoiced_lines(self, so_lines):
        domain = super()._analytic_line_domain_get_invoiced_lines(so_lines)
        param_invoiced_timesheet = self.env['ir.config_parameter'].sudo().get_str('sale.invoiced_timesheet') or DEFAULT_INVOICED_TIMESHEET
        if param_invoiced_timesheet == 'approved':
            domain = Domain.AND([domain, [('validated', '=', True)]])
        return domain
