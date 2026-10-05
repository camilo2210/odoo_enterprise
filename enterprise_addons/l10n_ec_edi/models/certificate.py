from cryptography import x509

from odoo import models


class CertificateCertificate(models.Model):
    _inherit = 'certificate.certificate'

    def _l10n_ec_edi_get_issuer_rfc_string(self):
        self.ensure_one()

        cert = x509.load_pem_x509_certificate(self.pem_certificate.content)
        return cert.issuer.rfc4514_string()
