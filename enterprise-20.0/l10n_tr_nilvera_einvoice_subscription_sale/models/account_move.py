from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_tr_nilvera_einvoice_check_invalid_subscription_dates(self):
        subscription_lines = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product' and line.deferred_start_date)
        return any(
            line.deferred_start_date != subscription_lines[0].deferred_start_date or
            line.deferred_end_date != subscription_lines[0].deferred_end_date
            for line in subscription_lines[1:]
        )
