from odoo.addons.iot.tests.common import IotCommonTest


class TestIotDevices(IotCommonTest):
    def _run_action_asserts(self, body: dict) -> dict:
        res = super()._run_action_asserts(body)
        if body.get("action") == "update_url":
            self.assertIn(
                "data",
                body,
                "The action to update the display URL should contain a 'data' key.",
            )
            self.assertIn(
                "update_url",
                body["data"],
                "The action to update the display URL should contain the new URL in the 'data' key.",
            )
        return res

    def test_iot_printer_test_button(self):
        """Ensure Printer "Test" button sends the correct message to the IoT Box."""
        self.start_iot_tour("/odoo/iot", "iot_device_test_printer", login="admin")

    def test_iot_display_update_url(self):
        """Ensure that the IoT Display receives the correct URL
        to display when the URL is updated on the IoT Display form.
        """
        self.env["iot.device"].sudo().create(
            {
                "name": "Display",
                "identifier": "mock_display",
                "iot_id": self.shop_iot_box.id,
                "type": "display",
                "connection": "hdmi",
                "connected_status": "connected",
            },
        )
        self.start_iot_tour("/odoo/iot", "iot_test_update_display_url", login="admin")

    def test_iot_fdm_test_button(self):
        """Ensure FDM "Test" button sends the correct message to the IoT Box."""
        self.env["iot.device"].sudo().create(
            {
                "name": "FDM",
                "identifier": "mock_fdm",
                "iot_id": self.shop_iot_box.id,
                "type": "fiscal_data_module",
                "connection": "serial",
                "connected_status": "connected",
            },
        )
        self.expected_ws_result = "000"
        self.start_iot_tour("/odoo/iot", "iot_device_test_fdm", login="admin")
        self.assertEqual(
            self.iot_websocket_messages[0].get("iot_action", {}).get("action"),
            "status",
            "Testing the FDM device should send an 'iot_action' message with the action 'status' to the IoT Box.",
        )
