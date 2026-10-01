from odoo import models


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _create_invoices(self, sale_orders):
        invoices = super()._create_invoices(sale_orders)
        # In the context of the bank rec widget, we want to automatically reconcile the invoice line
        if statement_id := self.env.context.get("bank_rec_widget_statement_line_id"):
            st_line = self.env['account.bank.statement.line'].browse(statement_id)
            move_lines = invoices.line_ids.filtered(lambda l: l.account_id.account_type in {'asset_receivable', 'liability_payable'})
            st_line.set_line_bank_statement_line(move_lines.ids)
        return invoices
