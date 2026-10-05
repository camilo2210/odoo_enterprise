from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _compute_name(self):
        # EXTENDS l10n_uy_edi, a POS invoice with no CFE must not consume a number of the DGI series
        no_cfe = self.filtered(lambda move:
            move.state == "posted"
            and move.journal_id.l10n_uy_edi_type == "electronic"
            and not move.l10n_latam_document_type_id
            and move.sudo().pos_order_ids,
        )
        super(AccountMove, self - no_cfe)._compute_name()
        for move in no_cfe:
            if not move.name or move.name == "/":
                move.name = "* %s" % move.id
