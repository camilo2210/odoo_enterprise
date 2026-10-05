from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # cron jobs
    def cron_run_sii_workflow(self):
        """
        This method groups all the steps needed to do the SII workflow:
        1.- Ask to SII for the status of the DTE sent
        """
        super(AccountMove, self).cron_run_sii_workflow()
        pick_skip = self.env['stock.picking'].with_context(cron_skip_connection_errs=True)
        pick_skip._l10n_cl_ask_dte_status()
