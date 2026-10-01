from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_be_intervat_ecb = fields.Char(
        string="Intervat VAT number",
        related='company_id.vat',
        readonly=False,
    )
    l10n_be_intervat_mode = fields.Selection(
        related='company_id.l10n_be_intervat_mode',
        readonly=False,
    )
    l10n_be_intervat_access_token = fields.Char(
        related='company_id.l10n_be_intervat_access_token',
    )
    account_representative_id = fields.Many2one(
        related='company_id.account_representative_id',
        readonly=False,
    )
    l10n_be_intervat_show_settings = fields.Boolean(related='company_id.l10n_be_intervat_show_settings')

    def action_close_intervat_connection(self):
        self.company_id.write({
            'l10n_be_intervat_refresh_token': None,
            'l10n_be_intervat_access_token': None,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self.env._("Intervat connection closed."),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
