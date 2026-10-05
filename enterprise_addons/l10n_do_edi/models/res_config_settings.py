from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_do_edi_web_service_env = fields.Selection(
        related='company_id.l10n_do_edi_web_service_env',
        readonly=False,
    )
    l10n_do_edi_username = fields.Char(
        related='company_id.l10n_do_edi_username',
        readonly=False,
    )
    l10n_do_edi_password = fields.Char(
        related='company_id.l10n_do_edi_password',
        readonly=False,
    )
    l10n_do_edi_key = fields.Char(
        related='company_id.l10n_do_edi_key',
        readonly=False,
    )
    l10n_do_edi_llave = fields.Char(
        related='company_id.l10n_do_edi_llave',
        readonly=False,
    )
