import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    analytic_distribution = fields.Json(
        string='Analytic Distribution',
        help="Analytic distribution for this payment. "
             "When the payment is linked to invoices it is automatically "
             "computed from the invoice analytic distribution. "
             "For manual payments this field must be filled manually.",
    )

    # ------------------------------------------------------------------
    # Posting enforcement
    # ------------------------------------------------------------------
    def action_post(self):
        """Block posting if analytic distribution is not set."""
        for payment in self:
            if not payment.analytic_distribution:
                raise UserError(_(
                    "Cannot post payment %(name)s.\n\n"
                    "The analytic distribution is not set.  Please configure "
                    "the analytic distribution before posting this payment.",
                    name=payment.display_name or _('New'),
                ))
        return super().action_post()

    # ------------------------------------------------------------------
    # Propagation to journal entry lines
    # ------------------------------------------------------------------
    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        """Inject analytic distribution into every payment journal-entry line."""
        line_vals_list = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
        )
        if self.analytic_distribution:
            for line_vals in line_vals_list:
                line_vals['analytic_distribution'] = self.analytic_distribution
        return line_vals_list

    def _synchronize_to_moves(self, changed_fields):
        """Propagate analytic distribution changes to the underlying
        ``account.move`` lines when the payment is edited."""
        super()._synchronize_to_moves(changed_fields)
        if 'analytic_distribution' not in changed_fields:
            return
        for payment in self.with_context(
            skip_account_move_synchronization=True,
        ):
            if not payment.move_id or not payment.analytic_distribution:
                continue
            target_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id
                and l.display_type not in ('line_section', 'line_note')
            )
            if target_lines:
                target_lines.write({
                    'analytic_distribution': payment.analytic_distribution,
                })
                _logger.info(
                    "Synced analytic distribution from payment %s to %d "
                    "move line(s) on %s",
                    payment.display_name,
                    len(target_lines),
                    payment.move_id.display_name,
                )
