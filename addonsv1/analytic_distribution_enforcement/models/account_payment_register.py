import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    analytic_distribution = fields.Json(
        string='Analytic Distribution',
        compute='_compute_analytic_distribution_from_invoices',
        store=True,
        readonly=False,
        help="Analytic distribution computed from the invoices being paid.  "
             "You can modify it before creating the payment.",
    )

    # ------------------------------------------------------------------
    # Compute from source invoices
    # ------------------------------------------------------------------
    @api.depends('line_ids')
    def _compute_analytic_distribution_from_invoices(self):
        """Compute a proportionally merged analytic distribution from the
        invoices / bills being paid."""
        for wizard in self:
            wizard.analytic_distribution = (
                wizard._get_merged_analytic_from_invoices()
            )

    def _get_merged_analytic_from_invoices(self):
        """Return a merged ``analytic_distribution`` dict weighted by the
        absolute balance of each product / service invoice line across
        all invoices being paid.

        Returns:
            dict | False: Merged distribution or ``False`` when empty.
        """
        moves = self.line_ids.mapped('move_id')
        if not moves:
            return False

        all_product_lines = self.env['account.move.line']
        for move in moves:
            product_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
                and l.analytic_distribution
            )
            all_product_lines |= product_lines

        if not all_product_lines:
            return False

        total_amount = sum(abs(l.balance) for l in all_product_lines)
        if not total_amount:
            return False

        merged = {}
        for line in all_product_lines:
            weight = abs(line.balance) / total_amount
            for acct_key, pct in (line.analytic_distribution or {}).items():
                merged[acct_key] = merged.get(acct_key, 0.0) + weight * pct

        _logger.info(
            "Computed merged analytic from %d invoice line(s): %s",
            len(all_product_lines), merged,
        )
        return merged or False

    # ------------------------------------------------------------------
    # Pass analytic to the payment being created
    # ------------------------------------------------------------------
    def _create_payment_vals_from_wizard(self, batch_result):
        """Inject analytic distribution into the payment values dict."""
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        if self.analytic_distribution:
            payment_vals['analytic_distribution'] = self.analytic_distribution
        return payment_vals
