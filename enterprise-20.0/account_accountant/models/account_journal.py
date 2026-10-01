from odoo import models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def action_open_auto_reconcile_wizard(self):
        self.ensure_one()
        wizard = self.env['bank.rec.auto.reconcile.wizard'].create({'journal_id': self.id})
        return wizard._get_records_action(target='new', name=self.env._("Run Auto Reconciliation"))
