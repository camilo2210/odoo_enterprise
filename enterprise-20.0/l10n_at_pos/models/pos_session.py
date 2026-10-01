from odoo import models, _
from odoo.exceptions import ValidationError


class PosSession(models.Model):
    _inherit = 'pos.session'

    def write(self, vals):
        if self.company_id.sudo().l10n_at_fiskaly_api_secret:
            # It will always asks first to close session before generating credentials so session is tried to be opened for the below cases
            if not self.company_id.sudo().l10n_at_fiskaly_access_token or not self.company_id.l10n_at_is_fon_authenticated:
                raise ValidationError(_("Please authenticate Fiskaly credentials & FON before starting any session."))
            if self.company_id.currency_id.rounding != 0.01:
                raise ValidationError(_("The currency rounding should be 0.01 to start a session with Fiskaly."))
        return super().write(vals)
