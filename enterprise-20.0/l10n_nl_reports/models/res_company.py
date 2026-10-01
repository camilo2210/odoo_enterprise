# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

import requests
from cryptography.hazmat.primitives import serialization
from requests import HTTPError

from odoo import fields, models, _
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import BinaryBytes


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_nl_reports_sbr_cert_id = fields.Many2one(
        string='Digipoort Certificate',
        comodel_name='certificate.certificate',
        domain=[('is_valid', "=", True)],
        help="Select the certificate that will be used to connect to the Digipoort infrastructure. "
             "The private key from this certificate will be used if one is included.",
    )
    l10n_nl_reports_sbr_server_root_cert_id = fields.Many2one(
        string='SBR Root Certificate',
        comodel_name='certificate.certificate',
        domain=[('is_valid', "=", True)],
        help="The SBR Tax Service Server Root Certificate is used to verifiy the connection with the Tax services server of the SBR."
             "It is used in order to make the connection library trust the server.",
    )
    l10n_nl_reports_sbr_last_sent_date_to = fields.Date(
        'Last Date Sent',
        help="Stores the date of the end of the last period submitted to the Tax Services",
        readonly=True
    )
    l10n_nl_reports_sbr_icp_last_sent_date_to = fields.Date(
        'Last Date Sent (ICP)',
        help="Stores the date of the end of the last period submitted to the Digipoort Services for ICP",
        readonly=True
    )
    l10n_nl_reports_tax_consultant_order = fields.Selection([
            ('NBA', 'NBA - Accountants'),
            ('RB', 'RB - Register of Tax Advisors'),
            ('NOB', 'NOB - Dutch Order of Tax Advisors'),
            ('NOAB', 'NOAB - Dutch Order of Administrative and Tax Experts'),
        ], default='NBA', required=True, string="Tax Consultant Order",
        help="The order of tax consultants the tax consultant belongs to."
    )

    def _l10n_nl_get_certificate_and_key_bytes(self):
        """Return personal SBR certificate/key PEM bytes, or ``(None, None)`` to use the IAP group certificate."""
        self.ensure_one()

        certificate = self.sudo().l10n_nl_reports_sbr_cert_id
        if not certificate:
            return (None, None)
        if not certificate.pem_certificate or not certificate.private_key_id.pem_key:
            raise RedirectWarning(
                _("The certificate or the private key is missing. Please upload it in the Accounting Settings first."),
                self.env.ref('account.action_account_config').id,
                _("Go to the Accounting Settings"),
            )
        # The certificate.key stores the PEM key encrypted whenever it has a password,
        # while the TLS handshake and the WSSE signature require it without a passphrase.
        private_key = serialization.load_pem_private_key(
            base64.b64decode(certificate.private_key_id.with_context(bin_size=False).pem_key),
            certificate.private_key_id.password.encode() if certificate.private_key_id.password else None,
        ).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return (
            base64.b64decode(certificate.with_context(bin_size=False).pem_certificate),
            private_key,
        )

    def _l10n_nl_get_server_root_certificate_bytes(self):
        """ Return the tax service server root certificate as PEM encoded bytes.
            Throws a UserError if the services are not reachable.
        """
        if not self.sudo().l10n_nl_reports_sbr_server_root_cert_id or not self.sudo().l10n_nl_reports_sbr_server_root_cert_id.is_valid:
            try:
                req_root = requests.get('https://cert.pkioverheid.nl/PrivateRootCA-G1.cer', timeout=30)
                req_root.raise_for_status()

                # This certificate is a .cer and is in DER format
                cert = self.env['certificate.certificate'].sudo().create({
                    'name': 'SBR Root Certificate',
                    'content': BinaryBytes(req_root.content),
                })
                self.write({'l10n_nl_reports_sbr_server_root_cert_id': cert.id})
            except HTTPError:
                raise UserError(_("The server root certificate is not accessible at the moment. Please try again later."))

        return self.sudo().l10n_nl_reports_sbr_server_root_cert_id.pem_certificate.content

    def _get_countries_allowing_tax_representative(self):
        rslt = super()._get_countries_allowing_tax_representative()
        rslt.add('NL')
        return rslt
