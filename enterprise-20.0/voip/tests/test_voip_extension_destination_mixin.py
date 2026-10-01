from odoo.addons.voip.tests.common_voip import VoipPhoneServiceCase


class TestVoipExtensionDestinationMixin(VoipPhoneServiceCase):
    """Exercised through `voip.call.group`, one of three inheritors
    (`res.users`, `voip.queue` share the exact same mixin logic)."""

    def _create_call_group(self, name="Group"):
        return self.env["voip.call.group"].create({"name": name})

    def test_setting_routing_extension_number_creates_an_extension(self):
        call_group = self._create_call_group()

        call_group.routing_extension_number = "105"

        extension = self.env["voip.extension"].search([
            ("destination_ref", "=", f"voip.call.group,{call_group.id}"),
        ])
        self.assertEqual(len(extension), 1)
        self.assertEqual(extension.number, "105")
        self.assertEqual(call_group.routing_extension_id, extension)
        self.assertTrue(call_group.has_routing_extension)

    def test_updating_routing_extension_number_reuses_the_same_extension(self):
        call_group = self._create_call_group()
        call_group.routing_extension_number = "105"
        first_extension = call_group.routing_extension_id

        call_group.routing_extension_number = "106"

        self.assertEqual(call_group.routing_extension_id, first_extension)
        self.assertEqual(call_group.routing_extension_id.number, "106")

    def test_clearing_routing_extension_number_deletes_the_extension(self):
        call_group = self._create_call_group()
        call_group.routing_extension_number = "105"
        extension = call_group.routing_extension_id

        call_group.routing_extension_number = False

        self.assertFalse(extension.exists())
        self.assertFalse(call_group.has_routing_extension)
        self.assertFalse(call_group.routing_extension_number)

    def test_search_routing_extension_number(self):
        with_extension = self._create_call_group("With extension")
        with_extension.routing_extension_number = "105"
        without_extension = self._create_call_group("Without extension")

        found = self.env["voip.call.group"].search([("routing_extension_number", "=", "105")])

        self.assertEqual(found, with_extension)
        self.assertNotIn(without_extension, found)

    def test_search_has_routing_extension(self):
        with_extension = self._create_call_group("With extension")
        with_extension.routing_extension_number = "105"
        without_extension = self._create_call_group("Without extension")

        found_true = self.env["voip.call.group"].search([("has_routing_extension", "=", True)])
        found_false = self.env["voip.call.group"].search([("has_routing_extension", "=", False)])

        self.assertIn(with_extension, found_true)
        self.assertNotIn(without_extension, found_true)
        self.assertIn(without_extension, found_false)
        self.assertNotIn(with_extension, found_false)

    def test_unlink_removes_the_routing_extension(self):
        call_group = self._create_call_group()
        call_group.routing_extension_number = "105"
        extension = call_group.routing_extension_id

        call_group.unlink()

        self.assertFalse(extension.exists())
