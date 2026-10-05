import logging

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        """Enforce analytic distribution on every product line before
        confirming the purchase order."""
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
                    "Cannot confirm purchase order %(order)s.\n\n"
                    "The following lines do not have analytic distribution:\n"
                    "%(lines)s\n\n"
                    "Please set the analytic distribution on all order lines "
                    "before confirming.",
                    order=order.name,
                    lines=names,
                ))
        return super().button_confirm()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_account_move_line(self, move=False):
        """Reinforce analytic distribution propagation from the
        purchase-order line to the vendor-bill line.

        The standard flow already propagates ``analytic_distribution`` in
        most scenarios, but this override guarantees it is never lost.
        """
        vals = super()._prepare_account_move_line(move=move)
        if self.analytic_distribution and not vals.get('analytic_distribution'):
            vals['analytic_distribution'] = self.analytic_distribution
            _logger.info(
                "Propagated analytic distribution from PO line '%s' "
                "(order %s) to vendor bill line",
                self.name, self.order_id.name,
            )
        return vals
