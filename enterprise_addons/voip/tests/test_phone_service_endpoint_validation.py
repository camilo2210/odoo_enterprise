from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.voip.models.phone_service_api import validate_phone_service_endpoint


@tagged("voip", "post_install", "-at_install")
class TestPhoneServiceEndpointValidation(TransactionCase):
    def test_accepts_an_odoo_com_https_endpoint(self):
        hostname = validate_phone_service_endpoint(self.env, "https://iap.odoo.com/api")
        self.assertEqual(hostname, "iap.odoo.com")

    def test_rejects_a_url_without_a_hostname(self):
        with self.assertRaisesRegex(UserError, "valid HTTPS URL"):
            validate_phone_service_endpoint(self.env, "not-a-url")

    def test_rejects_a_non_https_scheme_on_a_real_host(self):
        with self.assertRaisesRegex(UserError, "valid HTTPS URL"):
            validate_phone_service_endpoint(self.env, "http://iap.odoo.com/api")

    def test_rejects_a_host_outside_the_odoo_com_allowlist(self):
        with self.assertRaisesRegex(UserError, "not an allowed Odoo host"):
            validate_phone_service_endpoint(self.env, "https://evil.example.com/api")

    def test_accepts_http_on_dev_loopback_hosts(self):
        hostname = validate_phone_service_endpoint(self.env, "http://localhost:8080/api")
        self.assertEqual(hostname, "localhost")

    def test_rejects_a_non_http_scheme_on_a_loopback_host(self):
        with self.assertRaisesRegex(UserError, "valid HTTPS URL"):
            validate_phone_service_endpoint(self.env, "ftp://127.0.0.1/api")
