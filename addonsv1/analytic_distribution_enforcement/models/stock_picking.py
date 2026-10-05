import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    analytic_distribution = fields.Json(
        string='Analytic Distribution',
        help="Set analytic distribution at the picking level to apply it "
             "to all stock moves.  Individual moves can be customised "
             "afterwards.",
    )

    # ------------------------------------------------------------------
    # Propagation helpers
    # ------------------------------------------------------------------
    @api.onchange('analytic_distribution')
    def _onchange_analytic_distribution(self):
        """Propagate header-level analytic to every stock move (UI side)."""
        if self.analytic_distribution:
            for move in self.move_ids:
                move.analytic_distribution = self.analytic_distribution

    def write(self, vals):
        """Propagate analytic distribution to stock moves on write."""
        res = super().write(vals)
        if 'analytic_distribution' in vals and vals['analytic_distribution']:
            for picking in self:
                picking.move_ids.write({
                    'analytic_distribution': vals['analytic_distribution'],
                })
                _logger.info(
                    "Propagated analytic from picking %s to %d stock move(s)",
                    picking.display_name, len(picking.move_ids),
                )
        return res

    # ------------------------------------------------------------------
    # Validation enforcement
    # ------------------------------------------------------------------
    def button_validate(self):
        """Enforce analytic distribution on stock moves before validation."""
        for picking in self:
            picking._enforce_analytic_on_moves()
        return super().button_validate()

    def _enforce_analytic_on_moves(self):
        """Validate that every relevant stock move has analytic distribution.

        * Incoming / outgoing pickings → **all** non-cancelled moves.
        * Internal transfers → only moves whose product has automated
          (real-time) valuation, since only those generate journal entries.
        """
        self.ensure_one()
        moves_to_check = self.move_ids.filtered(
            lambda m: m.state != 'cancel'
        )

        if self.picking_type_code == 'internal':
            moves_to_check = moves_to_check.filtered(
                lambda m: (
                    m.product_id.categ_id.property_valuation == 'real_time'
                )
            )

        if not moves_to_check:
            return

        missing = moves_to_check.filtered(
            lambda m: not m.analytic_distribution
        )
        if missing:
            names = '\n'.join(
                '  • %s  (× %s)' % (
                    m.product_id.display_name or _('(No product)'),
                    m.product_uom_qty,
                )
                for m in missing[:15]
            )
            raise UserError(_(
                "Cannot validate %(picking)s.\n\n"
                "The following stock moves do not have analytic distribution:\n"
                "%(moves)s\n\n"
                "Please set the analytic distribution on all stock moves "
                "(or at the picking header level) before validating.",
                picking=self.display_name or _('New'),
                moves=names,
            ))


class StockMove(models.Model):
    _inherit = 'stock.move'

    # Field declaration — safe merge if the field already exists in
    # stock_account / purchase_stock / sale_stock.
    analytic_distribution = fields.Json(
        string='Analytic Distribution',
    )

    # ------------------------------------------------------------------
    # Propagation to valuation journal entries
    # ------------------------------------------------------------------
    def _prepare_account_move_vals(self, *args, **kwargs):
        """Inject analytic distribution from the stock move into every
        line of the valuation journal entry."""
        vals = super()._prepare_account_move_vals(*args, **kwargs)
        if not self.analytic_distribution:
            return vals
        for line_command in vals.get('line_ids', []):
            # Command format: (0, 0, {values}) for CREATE
            #                  (1, id, {values}) for UPDATE
            if (
                isinstance(line_command, (list, tuple))
                and len(line_command) >= 3
                and line_command[0] in (0, 1)
                and isinstance(line_command[2], dict)
            ):
                if not line_command[2].get('analytic_distribution'):
                    line_command[2]['analytic_distribution'] = (
                        self.analytic_distribution
                    )
        _logger.info(
            "Injected analytic from stock move %s into valuation entry",
            self.display_name,
        )
        return vals
