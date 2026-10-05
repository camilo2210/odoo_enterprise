from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ci_edi_company_parent_id = fields.Many2one(related='company_id.parent_id')
    l10n_ci_edi_server_mode = fields.Selection(
        related='company_id.l10n_ci_edi_server_mode',
        readonly=False,
    )
    l10n_ci_edi_fne_api_token = fields.Char(
        related='company_id.l10n_ci_edi_fne_api_token',
        readonly=False,
    )
