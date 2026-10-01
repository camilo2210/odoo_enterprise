from odoo.exceptions import UserError

from odoo.addons.obox.tests.common import CommonOboxTest
from odoo.addons.obox_android.models.obox_queue import _UNIQUE_ANDROID_ACTION_TYPES


class TestOboxAndroidQueue(CommonOboxTest):
    def _pending(self, action_type):
        return self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", action_type),
            ("status", "=", "pending"),
        ])

    def test_reloading_the_kiosk_queues_the_command(self):
        self.obox.action_kiosk_reload()

        self.assertEqual(len(self._pending("kiosk_reload")), 1)
        self.assertEqual(
            self._pending("kiosk_reload").payload["url"], "/odoo/kiosk_reload",
        )

    def test_a_kiosk_action_is_unique_per_box(self):
        self.obox.action_kiosk_reload()

        with self.assertRaises(UserError):
            self.obox.action_kiosk_reload()

    def test_every_android_unique_action_is_refused_while_one_is_waiting(self):
        for action_type in _UNIQUE_ANDROID_ACTION_TYPES:
            with self.subTest(action_type=action_type):
                self.obox._queue_action(action_type, f"/odoo/{action_type}")

                with self.assertRaises(UserError):
                    self.obox._queue_action(action_type, f"/odoo/{action_type}")

    def test_an_android_unique_action_is_unique_per_box_only(self):
        other_obox = self.env["obox.obox"].create({
            "name": "Other Obox",
            "serial_number": "OTHER",
            "state": "02_paired",
            "token": "other_obox_token",
        })
        self.obox.action_request_screenshot()

        other_obox.action_request_screenshot()

        self.assertEqual(len(self._pending("screenshot")), 1)

    def test_a_sync_request_is_not_an_android_unique_action(self):
        first = self.obox._queue_action("request_sync", "/odoo/sync")
        second = self.obox._queue_action("request_sync", "/odoo/sync")

        self.assertNotEqual(first, second)
