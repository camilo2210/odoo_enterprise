# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Amazon invoices are made simplified by default, as currently it is not possible
    # to get the vat number from the amazon api.
    # As the invoice, if standard, will likely fail when sending it to the SII due to
    # the lack of informations about the customer.
    def _compute_l10n_es_invoice_type(self):
        # EXTENDS 'l10n_es'
        super()._compute_l10n_es_invoice_type()
        for move in self:
            if any(move.line_ids.sale_line_ids.mapped('amazon_item_ref')):
                if move.move_type in ('out_invoice', 'in_invoice'):
                    move.l10n_es_invoice_type = 'F2'
                elif move.move_type in ('out_refund', 'in_refund'):
                    move.l10n_es_invoice_type = 'R5'
