from .common import CommonOboxTest


class TestOboxDiscoverDevices(CommonOboxTest):
    def test_new_device(self):
        self.obox.action_discover_devices()
        self.respond_to_pending_actions([{"identifier": "new_printer", "name": "New Printer", "type": "printer"}])
        new_printer = self.obox.device_ids.search([("identifier", "=", "new_printer")])

        self.assertIsNotNone(new_printer)
        self.assertEqual(new_printer.name, "New Printer")
        self.assertEqual(new_printer.type, "printer")

    def test_existing_device_with_new_type(self):
        self.obox.action_discover_devices()
        self.respond_to_pending_actions([{"identifier": "test_obox_printer", "name": "Not a Printer", "type": "scale"}])

        self.assertEqual(self.obox_printer.name, "Not a Printer")
        self.assertEqual(self.obox_printer.type, "scale")

    def test_existing_device_with_same_type(self):
        self.obox.action_discover_devices()
        self.respond_to_pending_actions([{"identifier": "test_obox_printer", "name": "New Name", "type": "printer"}])

        self.assertEqual(self.obox_printer.name, "Test Obox Printer")
