# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models


class AccountMoveSendBatchWizard(models.TransientModel):
    _inherit = 'account.move.send.batch.wizard'

    @api.depends('move_ids')
    def _compute_summary_data(self):
        # EXTENDS 'account'
        super()._compute_summary_data()
        for wizard in self:
            if not wizard.summary_data or not all(wizard.move_ids.mapped('l10n_ph_is_certificate_exportable')):
                continue
            wizard.summary_data = {
                key: {**value, 'noun': _("certificate(s)")}
                for key, value in wizard.summary_data.items()
            }
