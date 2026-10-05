from odoo import models, fields


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'

    l10n_do_edi_modification_code = fields.Selection(
        string="Modification Code",
        selection=[
            ('1', 'Cancels the modified NCF'),
            ('2', 'Corrects the text in modified fiscal receipt'),
            ('3', 'Corrects the amounts of the modified NCF'),
        ],
    )
    l10n_latam_use_documents = fields.Boolean(related='journal_id.l10n_latam_use_documents')

    def _prepare_default_values(self, move):
        values = super()._prepare_default_values(move)
        if self.country_code == 'DO' and self.l10n_do_edi_modification_code:
            values['l10n_do_edi_modification_code'] = self.l10n_do_edi_modification_code
        return values
