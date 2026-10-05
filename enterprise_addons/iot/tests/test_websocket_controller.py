import json
from unittest.mock import patch
from odoo.tests.common import HttpCase


class TestIotBoxSendWebsocket(HttpCase):
    def setUp(self):
        super().setUp()
        self.iot_box = self.env["iot.box"].create(
            {
                "name": "Test Box",
                "identifier": "test-box-001",
            }
        )
        self.iot_device = self.env["iot.device"].create(
            {
                "name": "Test Device",
                "identifier": "test-device-001",
                "iot_id": self.iot_box.id,
            }
        )

    def _post(self, payload):
        return self.url_open(
            "/iot/box/send_websocket",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": payload}),
            headers={"Content-Type": "application/json"},
        )

    # unknown box
    def test_unknown_box_returns_null(self):
        resp = self._post(
            {
                "session_id": "sess-001",
                "iot_box_identifier": "unknown-box",
                "device_identifier": "test-device-001",
                "status": "success",
            }
        )
        self.assertEqual(resp.status_code, 200)
        # Controller returns None implicitly → JSON-RPC wraps it as null
        self.assertIsNone(resp.json()["result"])

    # box found, device not found
    def test_unknown_device_returns_null(self):
        resp = self._post(
            {
                "session_id": "sess-002",
                "iot_box_identifier": "test-box-001",
                "device_identifier": "ghost-device",
                "status": "error",
            }
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["result"])

    # real box + real device
    def test_valid_request_calls_send_message(self):
        with patch(
            "odoo.addons.iot.models.iot_channel.IotChannel.send_message"
        ) as mock_send:
            resp = self._post(
                {
                    "session_id": "sess-003",
                    "iot_box_identifier": "test-box-001",
                    "device_identifier": "test-device-001",
                    "status": "success",
                    "message": "Print OK",
                    "result": {"pages": 2},
                }
            )
        self.assertEqual(resp.status_code, 200)
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        self.assertEqual(payload["session_id"], "sess-003")
        self.assertEqual(payload["message"]["status"], "success")

    # device_identifier matches box.identifier (targets box itself)
    def test_device_matching_box_identifier_is_allowed(self):
        with patch(
            "odoo.addons.iot.models.iot_channel.IotChannel.send_message"
        ) as mock_send:
            resp = self._post(
                {
                    "session_id": "sess-004",
                    "iot_box_identifier": "test-box-001",
                    "device_identifier": "test-box-001",  # targets the box itself
                    "status": "success",
                }
            )
        self.assertEqual(resp.status_code, 200)
        mock_send.assert_called_once()

    # session_id=None falls back to owner kwarg
    def test_session_id_fallback_to_owner(self):
        with patch(
            "odoo.addons.iot.models.iot_channel.IotChannel.send_message"
        ) as mock_send:
            resp = self._post(
                {
                    "session_id": None,
                    "iot_box_identifier": "test-box-001",
                    "device_identifier": "test-device-001",
                    "status": "success",
                    "owner": "legacy-owner-id",
                }
            )
        self.assertEqual(resp.status_code, 200)
        payload = mock_send.call_args[0][0]
        self.assertEqual(payload["session_id"], "legacy-owner-id")
