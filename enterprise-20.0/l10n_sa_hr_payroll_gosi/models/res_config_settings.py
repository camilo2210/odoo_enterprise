from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_sa_gosi_registration_number = fields.Char(related='company_id.l10n_sa_gosi_registration_number',
                                                   readonly=False)
    l10n_sa_gosi_api_key = fields.Char(related='company_id.l10n_sa_gosi_api_key', readonly=False)
    l10n_sa_gosi_client_id = fields.Char(related='company_id.l10n_sa_gosi_client_id', readonly=False)
    l10n_sa_gosi_client_secret = fields.Char(related='company_id.l10n_sa_gosi_client_secret', readonly=False)
    l10n_sa_gosi_dpop_private_key_id = fields.Many2one(related='company_id.l10n_sa_gosi_dpop_private_key_id',
                                                       readonly=False)
    l10n_sa_gosi_dpop_private_key_value = fields.Text(related='company_id.l10n_sa_gosi_dpop_private_key_value',
                                                      readonly=False)
    l10n_sa_gosi_api_mode = fields.Selection(related='company_id.l10n_sa_gosi_api_mode', readonly=False, required=True)
    l10n_sa_gosi_api_is_available = fields.Boolean(related='company_id.l10n_sa_gosi_api_is_available')

    def action_l10n_sa_gosi_test_connection(self):
        self.ensure_one()
        access_token = self.company_id._l10n_sa_gosi_get_access_token()
        if not access_token:
            test_result = self.env._('Oops! please check the registration number and try again.')
            notif_type = 'warning'
        else:
            test_result = self.env._('Connection Successful!')
            notif_type = 'success'

        return {
            'type': 'ir.actions.client',
            'tag': "display_notification",
            'params': {
                'title': self.env._("GOSI Test"),
                'message': test_result,
                'sticky': False,
                'type': notif_type,
                'next': {
                    'type': 'ir.actions.act_window_close',
                },
            },
        }
