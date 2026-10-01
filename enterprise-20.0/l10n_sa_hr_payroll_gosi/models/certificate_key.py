import base64
import json
import time
import uuid

from odoo import models
from odoo.exceptions import ValidationError


class CertificateKey(models.Model):
    _inherit = "certificate.key"

    def _l10n_sa_gosi_generate_dpop_jwt(self, method, url, ttl=10):
        def _b64url(val: bytes) -> str:
            return base64.urlsafe_b64encode(val).decode().rstrip("=")

        self.ensure_one()
        jwt_header = json.dumps({"typ": "dpop+jwt", "alg": 'RS256'}).encode()

        now = int(time.time())
        claims = {
            'iat': now,
            'nbf': now,
            'exp': now + ttl,
            'jti': str(uuid.uuid4()),
            'htu': url,
            'htm': method,
        }
        jwt_payload = json.dumps(claims).encode()
        unsigned_jwt = f"{_b64url(jwt_header)}.{_b64url(jwt_payload)}"
        try:
            jwt_signature = self._sign(unsigned_jwt.encode(), formatting='')
        except Exception as e:
            raise ValidationError(self.env._("Failed to generate JWT signature, please check the DPOP Private Key.")) from e

        return f"{unsigned_jwt}.{_b64url(jwt_signature)}"
