from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    peppol_reception_mode = fields.Selection(
        related='company_id.peppol_reception_mode',
        readonly=False,
    )
    documents_account_peppol_folder_id = fields.Many2one(
        related='company_id.documents_account_peppol_folder_id',
        check_company=True,
        readonly=False
    )
    documents_account_peppol_tag_ids = fields.Many2many(
        related='company_id.documents_account_peppol_tag_ids',
        readonly=False
    )

    @api.depends('peppol_reception_mode')
    def _compute_peppol_purchase_journal_required(self):
        # EXTENDS account_peppol
        super()._compute_peppol_purchase_journal_required()
        for config in self:
            if config.peppol_reception_mode == 'documents' and config.company_id._peppol_allows_document_reception():
                config.peppol_purchase_journal_required = False

    @api.onchange('peppol_reception_mode')
    def _onchange_peppol_reception_mode(self):
        if self.peppol_reception_mode == 'documents' and self.company_id._peppol_allows_document_reception():
            self.account_peppol_purchase_journal_id = False
        else:
            self.account_peppol_purchase_journal_id = self.company_id.peppol_purchase_journal_id
