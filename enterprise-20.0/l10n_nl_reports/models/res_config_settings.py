from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_nl_reports_sbr_use_own_certificate = fields.Boolean(
        string="Own Certificate",
        default=lambda self: bool(self.env.company.l10n_nl_reports_sbr_cert_id),
        store=False,
    )
    l10n_nl_reports_sbr_cert_id = fields.Many2one(related='company_id.l10n_nl_reports_sbr_cert_id', readonly=False)
    l10n_nl_rounding_difference_loss_account_id = fields.Many2one(
        comodel_name='account.account',
        related='company_id.l10n_nl_rounding_difference_loss_account_id',
        readonly=False,
        string="Dutch VAT Rounding Loss Account",
        help="Account used for losses from rounding the lines of Dutch tax reports",
    )
    l10n_nl_rounding_difference_profit_account_id = fields.Many2one(
        comodel_name='account.account',
        related='company_id.l10n_nl_rounding_difference_profit_account_id',
        readonly=False,
        string="Dutch VAT Rounding Profit Account",
        help="Account used for profits from rounding the lines of Dutch tax reports",
    )

    @api.onchange('l10n_nl_reports_sbr_use_own_certificate')
    def _onchange_l10n_nl_reports_sbr_use_own_certificate(self):
        if not self.l10n_nl_reports_sbr_use_own_certificate:
            self.l10n_nl_reports_sbr_cert_id = False
