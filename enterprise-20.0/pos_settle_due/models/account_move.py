from odoo import _, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def settle_invoices_from_pos(self, session_id, payment_data):
        """
        At this point payment_data is considered as valid and processed
        from the PoS, it can be used to create account.payment on orders
        """
        # All invoices are thought the same partner
        partner = self.env["res.partner"]._find_accounting_partner(self.mapped('partner_id')[:1])
        available_by_pm = {payment['payment_method_id']: payment['amount'] for payment in payment_data}
        session = self.env['pos.session'].browse(session_id)
        account_payments = self.env['account.payment']

        for invoice in self:
            remaining_amount = invoice.amount_residual
            invoice_payment_moves = self.env['account.move.line']
            for pm_id, amount in available_by_pm.items():
                if amount == 0:
                    continue

                pm = self.env['pos.payment.method'].browse(pm_id)
                payable = min(remaining_amount, amount)
                available_by_pm[pm_id] -= payable
                remaining_amount -= payable
                invoice_payment_moves |= pm._create_payment_line(
                    session,
                    payable,
                    partner.property_account_receivable_id,
                    _("Settling invoice %(invoice)s", invoice=invoice.name),
                    partner,
                )

                if remaining_amount <= 0:
                    break

            # Reconcile the payment lines against the invoice's receivable line,
            # mirroring pos_session._create_non_reconciled_order_picking() logic.
            # display_type='payment_term' is the receivable line on a posted invoice.
            invoice_receivable_lines = invoice.line_ids.filtered(
                lambda line: line.display_type == 'payment_term' and not line.reconciled
            )
            (invoice_receivable_lines | invoice_payment_moves)\
                .with_context(skip_invoice_sync=True)\
                .reconcile()

        return account_payments
