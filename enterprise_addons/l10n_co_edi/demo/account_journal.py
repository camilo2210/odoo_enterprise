from odoo import api, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.model
    def l10n_co_edi_archive_demo_journals(self):
        journals_to_archive = self.env['account.journal'].search([('code', 'in', ('INV', 'BILL')), ('country_code', '=', 'CO')])

        # Unlink draft entries
        if entries := self.env['account.move'].search([('journal_id', 'in', journals_to_archive.ids), ('state', 'in', ['draft'])]):
            entries.unlink()

        journals_to_archive.action_archive()
