from odoo import fields, models


class L10nGtEdiCancel(models.TransientModel):
    _name = 'l10n_gt_edi.cancel'
    _description = "Wizard to allow the cancellation of Guatemalan documents"

    l10n_gt_edi_cancel_reason = fields.Char(
        string="Cancel Reason",
        required=True,
        help="Reason to cancel this invoice.",
    )

    def button_cancel(self):
        move = self.env['account.move'].browse(self.env.context.get('active_id'))
        move._l10n_gt_edi_try_cancel(self.l10n_gt_edi_cancel_reason)
