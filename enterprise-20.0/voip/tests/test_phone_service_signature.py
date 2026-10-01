import base64
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.exceptions import Forbidden

from .common_voip import VoipPhoneServiceCase

from odoo.tests import tagged
from odoo.tools import hash_sign

from odoo.addons.voip.controllers.phone_service_api_controller import (
    decode_phone_service_event,
    PhoneServiceApiController,
)
from odoo.addons.voip.models.phone_service_api import CLIENT_SECRET_PARAM

SIGNATURE_LOGGER = "odoo.addons.voip.controllers.phone_service_api_controller"
# Spelled out rather than imported: the scope is half of a contract phone_service
# holds, so a change to it must fail these tests rather than follow along.
TOKEN_SCOPE = "phone_service_webhook"


@tagged("-at_install", "post_install")
class TestPhoneServiceSignature(VoipPhoneServiceCase):
    CLIENT_SECRET = "test_voip_client_secret"

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_str(CLIENT_SECRET_PARAM, self.CLIENT_SECRET)

    def _make_token(self, client_secret=None, payload=None, ttl=300):
        """Mint a token the way phone_service does."""
        return hash_sign(
            self.env(su=True),
            TOKEN_SCOPE,
            {"data": {"id": "evt_123"}, "meta": {}} if payload is None else payload,
            expiration=datetime.fromtimestamp(time.time() + ttl),
            secret=self.env["iap.account"]._hash_iap_token(
                client_secret or self.CLIENT_SECRET),
        )

    def _reject(self, token):
        """Drive the route as the webhook does; return the warnings it logged.

        Rejection is the route's job now: it holds every check the decoder does
        not, so it is the only place all three refusals can be observed.
        """
        with (
            patch(f"{SIGNATURE_LOGGER}.request", SimpleNamespace(env=self.env)),
            self.assertLogs(SIGNATURE_LOGGER, level="WARNING") as logs,
            self.assertRaises(Forbidden),
        ):
            PhoneServiceApiController().on_phone_service_event(token)
        return logs.output

    def test_valid_token(self):
        """A token signed with this database's secret yields its envelope."""
        payload = {"data": {"id": "evt_123"}, "meta": {}}
        self.assertEqual(
            decode_phone_service_event(
                self.env, self._make_token(payload=payload), self.CLIENT_SECRET),
            payload,
        )

    def test_token_signed_with_wrong_secret(self):
        """A token minted for another database is rejected, and the rejection is
        logged so a mis-provisioned DB is diagnosable."""
        token = self._make_token(client_secret="some_other_client_secret")
        self.assertIsNone(
            decode_phone_service_event(self.env, token, self.CLIENT_SECRET))
        logs = self._reject(token)
        self.assertEqual(len(logs), 1)
        self.assertIn("invalid or expired token", logs[0])

    def test_tampered_payload_is_rejected(self):
        """The envelope travels inside the signed token, so editing it in flight
        breaks the signature -- a captured token cannot carry a different event."""
        token = self._make_token(payload={"data": {"id": "evt_real"}, "meta": {}})
        raw = base64.urlsafe_b64decode(token + "===")
        tampered = base64.urlsafe_b64encode(
            raw.replace(b"evt_real", b"evt_fake")).decode().rstrip("=")
        logs = self._reject(tampered)
        self.assertEqual(len(logs), 1)
        self.assertIn("invalid or expired token", logs[0])

    def test_expired_token_is_rejected(self):
        """A replayed token is refused once its expiration has passed."""
        logs = self._reject(self._make_token(ttl=-1))
        self.assertEqual(len(logs), 1)
        self.assertIn("invalid or expired token", logs[0])

    def test_missing_token_is_logged(self):
        """A request that carries no token at all is rejected, not crashed on."""
        logs = self._reject(None)
        self.assertEqual(len(logs), 1)
        self.assertIn("missing or malformed token", logs[0])

    def test_non_string_token_is_logged(self):
        """JSON can put any type where the token belongs; none may raise."""
        for token in (1, [], {"token": "nested"}, True):
            with self.subTest(token=token):
                logs = self._reject(token)
                self.assertEqual(len(logs), 1)
                self.assertIn("missing or malformed token", logs[0])

    def test_malformed_token_is_logged(self):
        """Undecodable tokens are a logged 403, never an escaping exception: the
        route is public, and json2 serialises a traceback into its 500 body."""
        version_two = base64.urlsafe_b64encode(b"\x02" + b"0" * 48).decode().rstrip("=")
        for token in ("tooshort", "!!!!", "", "a", version_two, "AQ" * 40):
            with self.subTest(token=token):
                logs = self._reject(token)
                self.assertEqual(len(logs), 1)
                self.assertIn("invalid or expired token", logs[0])

    def test_missing_client_secret_is_logged(self):
        """When this DB never received a client secret, the rejection names the
        missing parameter so the operator knows why webhooks stopped."""
        token = self._make_token()
        self.env["ir.config_parameter"].sudo().set_str(CLIENT_SECRET_PARAM, "")
        logs = self._reject(token)
        self.assertEqual(len(logs), 1)
        self.assertIn(CLIENT_SECRET_PARAM, logs[0])

    def test_signing_key_derivation_is_pinned(self):
        """phone_service derives this key from its own copy of the client secret.
        Recomputing it here the way the controller does could never catch a drift
        between the two repos, so the expected value is written out."""
        self.assertEqual(
            self.env["iap.account"]._hash_iap_token("known_secret"),
            "52d9b9307d9c7496adb33fab539b90a7918f6a40",
        )

    def test_event_payload_is_not_logged(self):
        sensitive_value = "+32470000000"
        token = self._make_token(payload={
            "data": {
                "event_type": "unhandled_test_event",
                "id": "evt_sensitive_payload",
                "payload": {"phone_number": sensitive_value},
            },
            "meta": {},
        })
        with (
            patch(f"{SIGNATURE_LOGGER}.request", SimpleNamespace(env=self.env)),
            self.assertLogs(SIGNATURE_LOGGER, level="INFO") as logs,
        ):
            PhoneServiceApiController().on_phone_service_event(token)

        self.assertEqual(len(logs.output), 1)
        self.assertIn("unhandled_test_event", logs.output[0])
        self.assertIn("evt_sensitive_payload", logs.output[0])
        self.assertNotIn(sensitive_value, logs.output[0])
