from odoo.addons.iot.models.iot_box import IotBox
from odoo.addons.iot.tests.common import IotCommonTest
from odoo.addons.iot.wizard.add_iot_box import AddIotBox


class ConnectIotBox(IotCommonTest):
    connecting_iot_box_token = False

    def setUp(self):
        super().setUp()
        original_connect_iot_box = IotBox.connect_iot_box

        def mock_connect_iot_box(iot_box_self, _discovered_boxes):
            return original_connect_iot_box(
                iot_box_self,
                [
                    {
                        "pairing_code": "TOURCODE",
                        "serial_number": "tour-serial-number",
                    },
                ],
            )

        def mock__connect_iot_box_with_pairing_code(add_iot_box_self):
            self.connecting_iot_box_token = add_iot_box_self.token
            return add_iot_box_self._open_connecting_action()

        mock_connect_iot_box._api_model = True

        self.patch(IotBox, "connect_iot_box", mock_connect_iot_box)
        self.patch(
            AddIotBox, "_connect_iot_box_with_pairing_code", mock__connect_iot_box_with_pairing_code
        )

    def test_connect_button_with_auto_pair(self):
        """Make sure the connect button with auto pair creates a draft IoT Box record."""
        self.start_tour("/odoo/iot", "connect_button_with_auto_pair", login="admin")
        new_iot_box = self.env["iot.box"].search([("name", "ilike", "Connecting%")])
        self.assertEqual(
            len(new_iot_box),
            1,
            "A new draft record should have been created when clicking 'connect'",
        )
        self.assertFalse(
            new_iot_box.identifier,
            (
                "The draft IoT Box record should not contain the identifier of the IoT Box we're trying to connect"
                "in order for the wizard to close correctly when a new identifier has been found."
            ),
        )

        self.assertEqual(
            new_iot_box.token,
            self.connecting_iot_box_token,
            "The draft IoT Box record should contain the token generated",
        )

        # Simulate the IoT Box calling back the controller to create the final record w/ a printer device.
        mock_channel = self.url_open(
            "/iot/setup",
            json={
                "params": {
                    "iot_box": {
                        "identifier": "tour-serial-number",
                        "ip": "0.0.0.0",
                        "token": self.connecting_iot_box_token,
                        "version": "test",
                    },
                    "devices": {
                        "tour_printer": {
                            "name": "Tour receipt printer",
                            "type": "printer",
                            "connection": "network",
                        },
                    },
                },
            },
        )

        self.assertEqual(
            mock_channel.json().get("result"),
            "mock_iot_channel",
            "The /iot/setup controller should return the IoT WebSocket channel.",
        )

        new_iot_box = self.env["iot.box"].search(
            [("identifier", "=", "tour-serial-number")],
        )
        self.assertNotEqual(
            len(new_iot_box),
            0,
            "A new IoT Box record should be created when IoT Box calls /iot/setup",
        )

        self.assertEqual(
            new_iot_box.device_ids[0].type,
            "printer",
            "A printer device should be created when an IoT Box with a printer calls /iot/setup",
        )

    def test_unknown_iot_box_calls_back(self):
        unknown_identifier = "unknown-serial-number"
        mock_channel = self.url_open(
            "/iot/setup",
            json={
                "params": {
                    "iot_box": {
                        "identifier": unknown_identifier,
                        "ip": "0.0.0.0",
                        "token": "unknown-token",
                        "version": "test",
                    },
                    "devices": {
                        "unauthorized_display": {
                            "name": "Unauthorized display",
                            "type": "display",
                            "connection": "hdmi",
                        },
                    },
                },
            },
        )

        new_iot_box_count = self.env["iot.box"].search_count(
            [("identifier", "=", unknown_identifier)],
        )
        self.assertEqual(
            new_iot_box_count,
            0,
            "No new IoT Box record should be created for an unknown token",
        )

        unauthorized_printer_count = self.env["iot.device"].search_count(
            [("identifier", "=", "unauthorized_display")],
        )
        self.assertEqual(
            unauthorized_printer_count,
            0,
            "No device record should be created for an unknown IoT Box",
        )

        self.assertIsNone(
            mock_channel.json().get("result"),
            "No WebSocket channel should be returned to the unauthorized IoT Box",
        )
