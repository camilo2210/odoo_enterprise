from datetime import timedelta, timezone

from odoo import _, fields, models
from odoo.exceptions import UserError


class CertificateCertificate(models.Model):
    _inherit = 'certificate.certificate'

    scope = fields.Selection(
        selection_add=[
            ('cfdi_csd', 'CFDI (CSD)'),
            ('e_firma', 'E Firma (FIEL)'),
        ],
        ondelete={'cfdi_csd': 'set null', 'e_firma': 'set null'},
    )
    l10n_mx_edi_sat_token = fields.Char(readonly=True, copy=False)
    l10n_mx_edi_sat_token_expiry = fields.Datetime(readonly=True, copy=False)

    def _l10n_mx_edi_get_sat_token(self):
        """Returns SAT token from `self` if exists. If not we try to renew it.
        """
        self.ensure_one()
        now_utc = fields.Datetime.now(timezone.utc).replace(tzinfo=None)
        if (
            self.l10n_mx_edi_sat_token
            and self.l10n_mx_edi_sat_token_expiry
            and self.l10n_mx_edi_sat_token_expiry > now_utc + timedelta(seconds=30)
        ):
            return self.l10n_mx_edi_sat_token

        try:
            result = self.env['l10n_mx_edi.sat.download.client']._authenticate(self)
        except UserError as err:
            self.write({'l10n_mx_edi_sat_token': False, 'l10n_mx_edi_sat_token_expiry': False})
            raise UserError(_('Failed to renew Token. Authentication failed with: %s', err)) from err

        self.write({
            'l10n_mx_edi_sat_token': result['token'],
            'l10n_mx_edi_sat_token_expiry': result['expiry_date'].replace(tzinfo=None),
        })
        return result['token']
