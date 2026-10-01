from cryptography import x509

from odoo import models


class CertificateCertificate(models.Model):
    _inherit = 'certificate.certificate'

    def _get_issuer_string(self):
        self.ensure_one()

        cert = x509.load_pem_x509_certificate(self.pem_certificate.content)
        return cert.issuer.rfc4514_string()
