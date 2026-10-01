from odoo import fields, models


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    l10n_do_edi_modification_code = fields.Selection(
        string="Modification Code",
        selection=[
            ('1', 'Cancels the modified NCF'),
            ('2', 'Corrects the text in modified fiscal receipt'),
            ('3', 'Corrects the amounts of the modified NCF'),
        ],
    )

    def _prepare_default_reversal(self, move):
        values = super()._prepare_default_reversal(move)
        if self.country_code == 'DO' and self.l10n_do_edi_modification_code:
            values['l10n_do_edi_modification_code'] = self.l10n_do_edi_modification_code
        return values
