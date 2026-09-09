import logging

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Action override
    # ------------------------------------------------------------------
    def action_post(self):
        """Enforce analytic distribution and distribute to counterpart
        lines (CxC/CxP, taxes, withholdings) before posting."""
        for move in self:
            # 1. Auto-apply analytic from source documents (stock, landed cost)
            move._auto_apply_analytic_from_source()
            # 2. For invoices/bills, distribute analytic to counterpart lines
            if move.is_invoice(include_receipts=True):
                move._distribute_analytic_to_counterpart_lines()
            # 3. Final enforcement — block if any line still missing analytic
            move._enforce_analytic_distribution()
        return super().action_post()

    # ------------------------------------------------------------------
    # Auto-apply from source documents
    # ------------------------------------------------------------------
    def _auto_apply_analytic_from_source(self):
        """Auto-apply analytic distribution from linked source documents.

        Handles two scenarios:
        * Stock valuation entries  → inherits from ``stock.move``
        * Landed-cost entries      → inherits from cost lines (via context)
        """
        self.ensure_one()
        lines_without = self.line_ids.filtered(
            lambda l: l.account_id
            and not l.analytic_distribution
            and l.display_type not in ('line_section', 'line_note')
        )
        if not lines_without:
            return

        # --- Source 1: stock.move (valuation entries) ---
        stock_move = self.env['stock.move']
        if hasattr(self, 'stock_move_id'):
            stock_move = self.stock_move_id
        if stock_move and stock_move.analytic_distribution:
            lines_without.write({
                'analytic_distribution': stock_move.analytic_distribution,
            })
            _logger.info(
                "Auto-applied analytic from stock move %s to %d line(s) on %s",
                stock_move.display_name, len(lines_without), self.display_name,
            )
            return

        # --- Source 2: landed cost (via context set in button_validate) ---
        lc_analytic = self.env.context.get('landed_cost_analytic_distribution')
        if lc_analytic and isinstance(lc_analytic, dict):
            for _lc_id, merged_dist in lc_analytic.items():
                if merged_dist:
                    lines_without.write({
                        'analytic_distribution': merged_dist,
                    })
                    _logger.info(
                        "Auto-applied analytic from landed cost to %d line(s) "
                        "on %s",
                        len(lines_without), self.display_name,
                    )
                    return

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------
    def _enforce_analytic_distribution(self):
        """Block posting if any relevant line lacks analytic distribution.

        * Invoices/bills  → checks product / service lines only.
        * Journal entries → checks **all** lines that carry an account.
        """
        self.ensure_one()

        if self.is_invoice(include_receipts=True):
            product_lines = self.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
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
                    "Cannot post %(doc)s.\n\n"
                    "The following lines do not have analytic distribution:\n"
                    "%(lines)s\n\n"
                    "Please configure the analytic distribution on all "
                    "invoice lines before posting.",
                    doc=self.display_name or _('New'),
                    lines=names,
                ))
        else:
            lines_with_account = self.line_ids.filtered(
                lambda l: l.account_id
                and l.display_type not in ('line_section', 'line_note')
            )
            missing = lines_with_account.filtered(
                lambda l: not l.analytic_distribution
            )
            if missing:
                names = '\n'.join(
                    '  • [%s] %s' % (
                        l.account_id.code or '',
                        l.name or l.account_id.display_name or _('(No label)'),
                    )
                    for l in missing[:15]
                )
                raise UserError(_(
                    "Cannot post journal entry %(doc)s.\n\n"
                    "The following lines do not have analytic distribution:\n"
                    "%(lines)s\n\n"
                    "Please configure the analytic distribution on all "
                    "journal entry lines before posting.",
                    doc=self.display_name or _('New'),
                    lines=names,
                ))

    # ------------------------------------------------------------------
    # Proportional distribution to counterpart lines
    # ------------------------------------------------------------------
    def _compute_merged_analytic_distribution(self):
        """Compute a proportionally weighted merge of analytic distributions
        from product / service lines of an invoice.

        Each source line's analytic distribution is weighted by its absolute
        balance relative to the total absolute balance of all source lines.

        Returns:
            dict: ``{'analytic_account_id_str': percentage, ...}``
                  e.g. ``{'42': 60.0, '58': 40.0}``
        """
        self.ensure_one()
        source_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
            and l.analytic_distribution
        )
        if not source_lines:
            return {}

        total_abs_balance = sum(abs(line.balance) for line in source_lines)

        if not total_abs_balance:
            # All source lines have zero balance → even split
            count = len(source_lines)
            merged = {}
            for line in source_lines:
                for acct_key, pct in (line.analytic_distribution or {}).items():
                    merged[acct_key] = merged.get(acct_key, 0.0) + pct / count
            return merged

        merged = {}
        for line in source_lines:
            weight = abs(line.balance) / total_abs_balance
            for acct_key, pct in (line.analytic_distribution or {}).items():
                effective_pct = weight * pct
                merged[acct_key] = merged.get(acct_key, 0.0) + effective_pct

        _logger.info(
            "Merged analytic distribution for %s: %s (%d source lines)",
            self.display_name, merged, len(source_lines),
        )
        return merged

    def _distribute_analytic_to_counterpart_lines(self):
        """Apply the merged analytic distribution to counterpart lines:
        receivable / payable, taxes, withholdings, rounding, payment terms.

        Counterpart lines are those **not** in ``invoice_line_ids`` that
        have an accounting account set.
        """
        self.ensure_one()
        merged = self._compute_merged_analytic_distribution()
        if not merged:
            return

        source_ids = set(
            self.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
            ).ids
        )

        counterpart_lines = self.line_ids.filtered(
            lambda l: l.id not in source_ids
            and l.account_id
            and l.display_type not in ('line_section', 'line_note')
        )
        if not counterpart_lines:
            return

        counterpart_lines.write({'analytic_distribution': merged})
        _logger.info(
            "Distributed analytic to %d counterpart line(s) on %s "
            "(accounts: %s)",
            len(counterpart_lines),
            self.display_name,
            ', '.join(
                l.account_id.code or str(l.account_id.id)
                for l in counterpart_lines
            ),
        )
