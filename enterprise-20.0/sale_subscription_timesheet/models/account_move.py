# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_reinvoiced_analytic_lines_to_link(self):
        """This override extends the standard behavior by attempting to deduce
        a valid timesheet date range from the related sale orders when no explicit
        start or end date is provided in the context.

        If the invoice is linked to subscription orders containing timesheet-based
        products, analytic lines are searched per invoice line with an additional
        date filter derived from the sale order.

        When date deduction is not applicable, the default implementation is used.
        """
        analytic_lines = self.env['account.analytic.line']

        start_date = self.env.context.get('timesheet_start_date', False)
        end_date = self.env.context.get('timesheet_end_date', False)

        if (
            not start_date
            and not end_date
            and any(
                order_id._can_deduce_timesheet_range()
                for order_id in self.invoice_line_ids.sale_line_ids.order_id
            )
        ):
            for invoice_line_id in self.invoice_line_ids:
                so_lines = invoice_line_id.sale_line_ids.filtered(lambda line: line._is_line_reinvoicable())
                if not so_lines:
                    continue
                domain = self._analytic_line_domain_get_invoiced_lines(so_lines)

                if not start_date or not end_date:
                    start_date, end_date = so_lines.order_id._get_range_dates()

                if start_date:
                    domain = Domain.AND([Domain('date', '>=', start_date), domain])
                if end_date:
                    domain = Domain.AND([Domain('date', '<=', end_date), domain])

                analytic_lines |= self.env['account.analytic.line'].sudo().search(domain)
        else:
            analytic_lines = super()._get_reinvoiced_analytic_lines_to_link()

        return analytic_lines
