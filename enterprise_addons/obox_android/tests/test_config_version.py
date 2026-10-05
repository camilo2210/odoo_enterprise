from odoo.addons.obox.tests.common import CommonOboxTest


class TestOboxConfigVersion(CommonOboxTest):

    def test_stable_across_reads(self):
        first = self.obox.config_version
        self.obox.invalidate_recordset()
        self.assertEqual(self.obox.config_version, first)

    def test_changes_with_the_pin(self):
        before = self.obox.config_version
        self.obox.kiosk_pin = "4242"
        self.assertNotEqual(self.obox.config_version, before)

    def test_changes_with_the_name(self):
        before = self.obox.config_version
        self.obox.name = "Renamed"
        self.assertNotEqual(self.obox.config_version, before)

    def test_returning_to_an_earlier_config_returns_its_version(self):
        original = self.obox.config_version
        self.obox.kiosk_pin = "4242"
        self.obox.kiosk_pin = False
        self.assertEqual(self.obox.config_version, original)

    def test_synced_once_the_box_echoes_the_version(self):
        self.assertFalse(self.obox.config_synced)
        self.obox._sync_device_state({"config_version": self.obox.config_version})
        self.assertTrue(self.obox.config_synced)

    def test_a_config_change_desyncs_a_box_running_the_old_one(self):
        self.obox._sync_device_state({"config_version": self.obox.config_version})
        self.assertTrue(self.obox.config_synced)

        self.obox.kiosk_pin = "4242"
        self.assertFalse(self.obox.config_synced)

    def test_changes_when_a_device_is_renamed(self):
        before = self.obox.config_version
        self.obox_printer.name = "Caisse 2"
        self.assertNotEqual(self.obox.config_version, before)

    def test_a_device_is_listed_with_its_name(self):
        self.assertIn(
            {"identifier": "test_obox_printer", "name": "Test Obox Printer"},
            self.obox.config["devices"],
        )

    def test_a_pin_set_on_the_tablet_is_adopted(self):
        self.obox._sync_device_state({"kiosk": {"enabled": True, "kiosk_pin": "4242"}})

        self.assertEqual(self.obox.kiosk_pin, "4242")
        self.assertTrue(self.obox.has_kiosk_pin)

    def test_the_adopted_pin_is_what_travels_back_down(self):
        self.obox._sync_device_state({"kiosk": {"enabled": True, "kiosk_pin": "4242"}})

        self.assertEqual(self.obox.config["kiosk_pin"], "4242")

    def test_odoo_keeps_the_last_word_on_the_pin(self):
        self.obox.kiosk_pin = "1234"

        self.obox._sync_device_state({"kiosk": {"enabled": True, "kiosk_pin": "4242"}})

        self.assertEqual(self.obox.kiosk_pin, "1234")

    def test_a_pin_changed_on_an_up_to_date_box_is_adopted(self):
        self.obox.kiosk_pin = "1234"
        applied = self.obox.config_version

        self.obox._sync_device_state({
            "config_version": applied,
            "kiosk": {"enabled": True, "kiosk_pin": "4242"},
        })

        self.assertEqual(self.obox.kiosk_pin, "4242")

    def test_a_box_behind_odoo_does_not_overwrite_the_pin_odoo_just_set(self):
        self.obox.kiosk_pin = "1234"
        applied = self.obox.config_version
        self.obox.kiosk_pin = "5678"

        self.obox._sync_device_state({
            "config_version": applied,
            "kiosk": {"enabled": True, "kiosk_pin": "1234"},
        })

        self.assertEqual(self.obox.kiosk_pin, "5678")

    def test_adopting_a_changed_pin_does_not_ask_the_box_to_push_again(self):
        self.obox.platform = "android"
        self.obox.kiosk_pin = "1234"
        applied = self.obox.config_version
        self.env["obox.queue"].search([("obox_id", "=", self.obox.id)]).unlink()

        self.obox._sync_device_state({
            "config_version": applied,
            "kiosk": {"enabled": True, "kiosk_pin": "4242"},
        })

        self.assertEqual(self.obox.kiosk_pin, "4242")
        self.assertFalse(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "request_sync"),
        ]))

    def test_a_box_with_no_pin_does_not_clear_the_one_odoo_holds(self):
        self.obox.kiosk_pin = "1234"

        self.obox._sync_device_state({"kiosk": {"enabled": True, "kiosk_pin": ""}})

        self.assertEqual(self.obox.kiosk_pin, "1234")

    def test_adopting_a_pin_does_not_ask_the_box_to_push_again(self):
        self.obox.platform = "android"
        self.env["obox.queue"].search([("obox_id", "=", self.obox.id)]).unlink()

        self.obox._sync_device_state({"kiosk": {"enabled": True, "kiosk_pin": "4242"}})

        self.assertFalse(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "request_sync"),
        ]))

    def test_no_pin_means_no_pin(self):
        self.assertFalse(self.obox.has_kiosk_pin)
