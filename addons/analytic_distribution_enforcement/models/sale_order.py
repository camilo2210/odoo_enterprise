import logging

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Enforce analytic distribution on every product line before
        confirming the sales order."""
        for order in self:
            product_lines = order.order_line.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
                and l.product_id
            )
            missing = product_lines.filtered(
                lambda l: not l.analytic_distribution
            )
            if missing:
                names = '\n'.join(
                    '  • %s' % (
                        l.name
                        or (l.product_id.display_name if l.product_id else False)
                        or _('(No description)')
                    )
                    for l in missing[:15]
                )
                raise UserError(_(
                    "Cannot confirm sales order %(order)s.\n\n"
                    "The following lines do not have analytic distribution:\n"
                    "%(lines)s\n\n"
                    "Please set the analytic distribution on all order lines "
                    "before confirming.",
                    order=order.name,
                    lines=names,
                ))
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        """Reinforce analytic distribution propagation from the sales-order
        line to the invoice line.

        The standard flow already propagates ``analytic_distribution`` in
        most scenarios, but this override guarantees it is never lost.
        """
        vals = super()._prepare_invoice_line(**optional_values)
        if self.analytic_distribution and not vals.get('analytic_distribution'):
            vals['analytic_distribution'] = self.analytic_distribution
            _logger.info(
                "Propagated analytic distribution from SO line '%s' "
                "(order %s) to invoice line",
                self.name, self.order_id.name,
            )
        return vals
