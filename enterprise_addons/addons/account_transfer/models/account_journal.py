from odoo import models, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.ondelete(at_uninstall=True)
    def _unlink_cascade_transfer_model(self):
        if self.env.context.get('force_delete'):  # only cascade when switching CoA
            self.env['account.transfer.model'].search([('journal_id', 'in', self.ids)]).unlink()
