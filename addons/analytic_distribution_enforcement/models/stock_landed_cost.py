import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    def button_validate(self):
        """Enforce analytic distribution on cost lines and pass the merged
        distribution via context so the generated journal entry lines
        receive it automatically."""
        for landed_cost in self:
            landed_cost._enforce_analytic_on_cost_lines()

        # Build a mapping {landed_cost_id: merged_distribution} and
        # inject it via context for account.move.action_post() to consume.
        analytic_data = {}
        for lc in self:
            merged = lc._compute_merged_cost_analytic()
            if merged:
                analytic_data[str(lc.id)] = merged

        if analytic_data:
            self = self.with_context(
                landed_cost_analytic_distribution=analytic_data,
            )

        return super(StockLandedCost, self).button_validate()

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------
    def _enforce_analytic_on_cost_lines(self):
        """Block validation if any cost line lacks analytic distribution."""
        self.ensure_one()
        missing = self.cost_lines.filtered(
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
                "Cannot validate landed cost %(name)s.\n\n"
                "The following cost lines do not have analytic distribution:\n"
                "%(lines)s\n\n"
                "Please set the analytic distribution on all cost lines "
                "before validating.",
                name=self.display_name or _('New'),
                lines=names,
            ))

    # ------------------------------------------------------------------
    # Merge computation
    # ------------------------------------------------------------------
    def _compute_merged_cost_analytic(self):
        """Compute a proportionally weighted merge of analytic distributions
        from the cost lines, weighted by ``price_unit``.

        Returns:
            dict: Merged analytic distribution or empty dict.
        """
        self.ensure_one()
        lines_with_analytic = self.cost_lines.filtered('analytic_distribution')
        if not lines_with_analytic:
            return {}

        total = sum(abs(l.price_unit) for l in lines_with_analytic)
        if not total:
            return {}

        merged = {}
        for line in lines_with_analytic:
            weight = abs(line.price_unit) / total
            for acct_key, pct in (line.analytic_distribution or {}).items():
                merged[acct_key] = merged.get(acct_key, 0.0) + weight * pct

        _logger.info(
            "Merged analytic for landed cost %s: %s (%d cost lines)",
            self.display_name, merged, len(lines_with_analytic),
        )
        return merged


class StockLandedCostLines(models.Model):
    _inherit = 'stock.landed.cost.lines'

    # Field declaration — adds analytic_distribution to cost lines
    # if not already present from a base module.
    analytic_distribution = fields.Json(
        string='Analytic Distribution',
    )
