from odoo import api, fields, models


class L10n_Uy_EdiDocument(models.Model):
    _inherit = "l10n_uy_edi.document"

    pos_order_id = fields.Many2one("pos.order", readonly=True)

    # Compute methods

    @api.depends(
        "pos_order_id.l10n_uy_edi_document_number", "pos_order_id.amount_total",
        "pos_order_id.company_id", "pos_order_id.partner_id",
    )
    def _compute_from_origin(self):
        # EXTENDS 'l10n_uy_edi'
        super()._compute_from_origin()
        for doc in self:
            if doc.pos_order_id:
                doc.l10n_latam_document_number = doc.pos_order_id.l10n_uy_edi_document_number
                doc.l10n_latam_document_type_id = doc.pos_order_id._l10n_uy_edi_get_document_type()
                doc.company_id = doc.pos_order_id.company_id
                doc.partner_id = doc.pos_order_id.partner_id.commercial_partner_id

    # Helpers

    def _get_origin_record(self):
        # EXTENDS 'l10n_uy_edi'
        return super()._get_origin_record() or self.pos_order_id

    def _get_xml_attachment_name(self):
        # EXTENDS 'l10n_uy_edi': the base name reads the demo environment off the move
        if self.pos_order_id and self.pos_order_id.company_id.l10n_uy_edi_ucfe_env == "demo":
            return "demo-cfe-%s.xml" % self.l10n_latam_document_number
        if self.pos_order_id and self.state not in ("received", "accepted"):
            return "preview-cfe-pos-order-%s.xml" % self.pos_order_id.id
        return super()._get_xml_attachment_name()

    def action_update_dgi_state(self):
        # EXTENDS 'l10n_uy_edi': the terminal of a POS order is the one of its point of sale
        pos_docs = self.filtered("pos_order_id")
        for edi_doc in pos_docs:
            result = edi_doc._ucfe_inbox(
                "360", {"Uuid": edi_doc.uuid},
                terminal_code=edi_doc.pos_order_id.config_id.journal_id.l10n_uy_edi_ucfe_terminal_code,
            )
            edi_doc._update_cfe_state(result)
        return super(L10n_Uy_EdiDocument, self - pos_docs).action_update_dgi_state()
