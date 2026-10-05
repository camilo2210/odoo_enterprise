# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    l10n_br_related_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Related Invoice",
        copy=False,
        check_company=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
        help="Brazil: the NF-e covering the goods in this transfer. Filled in automatically once "
        "SEFAZ authorizes the invoice; packages assigned to their own invoice take precedence.",
    )

    def _l10n_br_is_shippable_nfe(self, invoice):
        """An NF-e whose key can be referenced on a shipping label."""
        return (
            invoice.state == "posted"
            and invoice.move_type == "out_invoice"
            and invoice.l10n_br_last_edi_status == "accepted"
            and not invoice.l10n_br_is_service_transaction
            and invoice.journal_id.l10n_br_invoice_serial
        )

    def _l10n_br_get_origin_invoice(self, package_name=False):
        """Find the correct invoice associated with this picking. It's entirely possible this picking
        is attached to invoices that aren't sent via Avalara, so we need to differentiate between
        "Not sent yet" and "won't ever be sent".
        """
        self.ensure_one()
        package = self.move_line_ids.result_package_id.filtered(lambda p: p.name == package_name)
        candidate_invoices = (
            package.l10n_br_move_id or
            self.l10n_br_related_move_id or
            self.move_ids.sale_line_id.invoice_lines.move_id
        )
        needs_nfe = not candidate_invoices or bool(candidate_invoices.fiscal_position_id.filtered("l10n_br_is_avatax"))
        accepted_invoice = candidate_invoices.filtered(self._l10n_br_is_shippable_nfe)
        return needs_nfe, accepted_invoice if len(accepted_invoice) == 1 else self.env["account.move"]

    def _l10n_br_has_missing_nfe_packages(self):
        """Check if there are packages missing their NF-e."""
        self.ensure_one()
        package_names = self.move_line_ids.result_package_id.mapped("name")
        if self.weight_bulk:
            package_names.append(False)  # Check for Bulk Content
        return any(
            needs_nfe and not invoice
            for needs_nfe, invoice in map(self._l10n_br_get_origin_invoice, package_names)
        )
