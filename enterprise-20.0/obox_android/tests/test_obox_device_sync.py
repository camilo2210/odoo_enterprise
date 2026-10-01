from odoo.tests import HttpCase, tagged

from odoo.addons.obox.tests.common import CommonOboxTest


def devices(ids=(), added=()):
    return {
        "ids": list(ids),
        "added": [
            entry if isinstance(entry, dict) else {"identifier": entry, "type": "printer"}
            for entry in added
        ],
    }


class TestOboxDeviceSync(CommonOboxTest):

    def _identifiers(self):
        return set(self.obox.device_ids.mapped("identifier"))

    def _push(self, block):
        self.obox._sync_device_state({"config_version": self.obox.config_version, "devices": block})

    def test_added_creates_the_device(self):
        self._push(devices(
            ids=["test_obox_printer", "test_obox_scale", "usb_04b8_0202_a"],
            added=[{"identifier": "usb_04b8_0202_a", "type": "printer", "name": "Epson TM"}],
        ))
        new = self.obox.device_ids.filtered(lambda d: d.identifier == "usb_04b8_0202_a")
        self.assertEqual(new.name, "Epson TM")
        self.assertEqual(new.type, "printer")

    def test_ids_alone_creates_nothing(self):
        self._push(devices(ids=["test_obox_printer", "ghost_device"]))
        self.assertNotIn("ghost_device", self._identifiers())

    def test_a_device_the_box_no_longer_reports_is_kept(self):
        self._push(devices(ids=["test_obox_printer"]))

        self.assertEqual(self._identifiers(), {"test_obox_printer", "test_obox_scale"})
        self.assertTrue(self.obox_scale.exists())

    def test_a_push_that_declares_nothing_leaves_every_name_alone(self):
        self.obox_printer.name = "Renamed in Odoo"

        self._push(devices(ids=["test_obox_printer", "test_obox_scale"]))

        self.assertEqual(self.obox_printer.name, "Renamed in Odoo")

    def test_a_re_declared_device_takes_the_name_it_carries(self):
        self.obox_printer.name = "Renamed in Odoo"

        self._push(devices(
            ids=["test_obox_printer", "test_obox_scale"],
            added=[{"identifier": "test_obox_printer", "type": "printer", "name": "Caisse 2"}],
        ))

        self.assertEqual(self.obox_printer.name, "Caisse 2")

    def test_an_outdated_box_does_not_undo_a_rename_made_in_odoo(self):
        outdated = self.obox.config_version
        self.obox_printer.name = "Renamed in Odoo"

        self.obox._sync_device_state({"config_version": outdated, "devices": devices(
            ids=["test_obox_printer", "test_obox_scale"],
            added=[{"identifier": "test_obox_printer", "type": "printer", "name": "Caisse 2"}],
        )})

        self.assertEqual(self.obox_printer.name, "Renamed in Odoo")

    def test_an_outdated_box_still_declares_a_new_device(self):
        self.obox._sync_device_state({"config_version": "outdated", "devices": devices(
            ids=["usb_04b8_0202_a"],
            added=[{"identifier": "usb_04b8_0202_a", "type": "printer", "name": "Epson TM"}],
        )})

        new = self.obox.device_ids.filtered(lambda d: d.identifier == "usb_04b8_0202_a")
        self.assertEqual(new.name, "Epson TM")

    def test_an_up_to_date_box_renames_itself(self):
        self.obox._sync_device_state({"config_version": self.obox.config_version, "name": "Counter tablet"})

        self.assertEqual(self.obox.name, "Counter tablet")

    def test_a_box_renaming_itself_is_not_asked_to_sync_again(self):
        self.obox.services = ["odoo", "sync"]

        self.obox._sync_device_state({"config_version": self.obox.config_version, "name": "Counter tablet"})

        self.assertFalse(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id), ("action_type", "=", "request_sync"),
        ]))

    def test_an_outdated_box_keeps_the_name_given_in_odoo(self):
        outdated = self.obox.config_version
        self.obox.name = "Renamed in Odoo"

        self.obox._sync_device_state({"config_version": outdated, "name": "Counter tablet"})

        self.assertEqual(self.obox.name, "Renamed in Odoo")
        self.assertEqual(self.obox._config_response()["config"]["name"], "Renamed in Odoo")

    def test_declaring_one_device_does_not_touch_another(self):
        self.obox_scale.name = "Renamed in Odoo"

        self._push(devices(
            ids=["test_obox_printer", "test_obox_scale"],
            added=[{"identifier": "test_obox_printer", "type": "printer", "name": "Caisse 2"}],
        ))

        self.assertEqual(self.obox_scale.name, "Renamed in Odoo")

    def test_a_declared_device_with_no_name_falls_back_to_its_identifier(self):
        self._push(devices(ids=["usb_ghost"], added=["usb_ghost"]))

        created = self.obox.device_ids.filtered(lambda d: d.identifier == "usb_ghost")
        self.assertEqual(created.name, "usb_ghost")

    def test_idempotent(self):
        block = devices(ids=["test_obox_printer", "test_obox_scale"])
        before = self.obox.device_ids.ids
        self._push(block)
        self._push(block)
        self.assertEqual(self.obox.device_ids.ids, before)

    def test_a_box_push_does_not_queue_a_state_request(self):
        self.obox.platform = "android"
        self.obox.services = ["odoo", "sync"]
        self.env["obox.queue"].search([("obox_id", "=", self.obox.id)]).unlink()

        self._push(devices(
            ids=["test_obox_printer", "test_obox_scale"],
            added=[{"identifier": "test_obox_printer", "type": "printer", "name": "Caisse 2"}],
        ))

        self.assertFalse(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "request_sync"),
        ]))

    def test_an_odoo_rename_asks_the_box_to_push(self):
        self.obox.platform = "android"
        self.obox.services = ["odoo", "sync"]
        self.env["obox.queue"].search([("obox_id", "=", self.obox.id)]).unlink()

        self.obox_printer.name = "Caisse 2"

        self.assertTrue(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "request_sync"),
        ]))


class TestOboxSyncPayload(CommonOboxTest):

    def test_a_delta_merges_into_the_stored_state(self):
        self.obox._sync_device_state({"ip": "10.0.0.9", "hardware": {"model": "C20Pro"}}, full=True)
        self.obox._sync_device_state({"ip": "10.0.0.42"})

        self.assertEqual(self.obox.device_state["ip"], "10.0.0.42")
        self.assertEqual(self.obox.device_state["hardware"]["model"], "C20Pro")

    def test_a_full_push_replaces_the_stored_state(self):
        self.obox._sync_device_state({"ip": "10.0.0.9", "hardware": {"model": "C20Pro"}}, full=True)
        self.obox._sync_device_state({"ip": "10.0.0.42"}, full=True)

        self.assertNotIn("hardware", self.obox.device_state)

    def test_the_address_follows_the_payload(self):
        self.obox._sync_device_state({"ip": "10.0.0.42", "local_port": 8071})

        self.assertEqual(self.obox.local_ip, "10.0.0.42")
        self.assertEqual(self.obox.local_port, 8071)

    def test_the_device_block_does_not_pollute_the_stored_state(self):
        self.obox._sync_device_state({"ip": "10.0.0.9", "devices": devices(ids=["test_obox_printer"])})

        self.assertNotIn("devices", self.obox.device_state)


@tagged("post_install", "-at_install")
class TestOboxDeviceSyncRoutes(HttpCase, CommonOboxTest):

    def _rpc(self, route, params):
        return self.make_jsonrpc_request(route, params)

    def _credentials(self, **extra):
        return {"serial_number": "TEST", "token": "test_obox_token", **extra}

    def test_connect_stores_local_port(self):
        self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", local_port=8070, services=["odoo"],
        ))
        self.assertEqual(self.obox.local_ip, "10.0.0.9")
        self.assertEqual(self.obox.local_port, 8070)

    def test_connect_without_port_defaults_to_zero(self):
        self._rpc("/obox/connect", self._credentials(local_ip="10.0.0.9", services=["odoo"]))
        self.assertEqual(self.obox.local_port, 0)

    def test_connect_records_declared_platform(self):
        self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo"], platform="android",
        ))
        self.assertEqual(self.obox.platform, "android")
        self.assertTrue(self.obox.is_android)

    def test_connect_without_platform_stays_rpi(self):
        """The Pi does not declare one, so silence must not flip the record."""
        self._rpc("/obox/connect", self._credentials(local_ip="10.0.0.9", services=["odoo"]))
        self.assertEqual(self.obox.platform, "rpi")
        self.assertFalse(self.obox.is_android)

    def test_connect_ignores_unknown_platform(self):
        self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo"], platform="toaster",
        ))
        self.assertEqual(self.obox.platform, "rpi")

    def test_connect_names_a_box_that_is_pairing(self):
        self.obox.state = "01_pairing"

        self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo", "sync"], name="Counter tablet",
        ))

        self.assertEqual(self.obox.name, "Counter tablet")

    def test_connect_does_not_rename_a_paired_box(self):
        self.obox.name = "Renamed in Odoo"

        response = self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo", "sync"], name="Counter tablet",
        ))

        self.assertEqual(self.obox.name, "Renamed in Odoo")
        self.assertEqual(response["config"]["name"], "Renamed in Odoo")

    def test_connect_hands_back_the_config(self):
        response = self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo", "sync"], platform="android",
        ))
        self.assertEqual(
            [device["identifier"] for device in response["config"]["devices"]],
            ["test_obox_printer", "test_obox_scale"],
        )
        self.assertEqual(response["config_version"], self.obox.config_version)

    def test_connect_returns_exactly_the_config_response(self):
        response = self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo", "sync"], platform="android",
        ))

        self.obox.invalidate_recordset()
        self.assertEqual(response, self.obox._config_response())
        self.assertFalse(response["config_up_to_date"])

    def test_connect_returns_nothing_to_a_box_that_does_not_sync(self):
        response = self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo"],
        ))

        self.assertIsNone(response)

    def test_connect_does_not_ask_an_android_box_to_discover(self):
        self._rpc("/obox/connect", self._credentials(
            local_ip="10.0.0.9", services=["odoo", "sync"], platform="android",
        ))
        self.assertFalse(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "discover_devices"),
        ]))

    def test_connect_asks_a_pi_to_discover(self):
        self._rpc("/obox/connect", self._credentials(local_ip="10.0.0.9", services=["odoo"]))

        self.assertEqual(self.obox.state, "02_paired")
        self.assertTrue(self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "discover_devices"),
        ]))

    def test_sync_push_alone_does_not_make_a_box_android(self):
        self._rpc("/obox/sync", self._credentials(state={"ip": "10.0.0.9"}, full=True))
        self.assertTrue(self.obox.device_state)
        self.assertFalse(self.obox.is_android)

    def test_sync_push_reconciles_the_device_list(self):
        self._rpc("/obox/sync", self._credentials(state={
            "ip": "10.0.0.9",
            "devices": devices(
                ids=["usb_04b8_0202_s"],
                added=[{"identifier": "usb_04b8_0202_s", "type": "printer", "name": "Epson TM"}],
            ),
        }))
        self.assertIn("usb_04b8_0202_s", self.obox.device_ids.mapped("identifier"))

    def test_sync_returns_the_config_when_the_box_is_behind(self):
        response = self._rpc("/obox/sync", self._credentials(state={"ip": "10.0.0.9"}))
        self.assertFalse(response["config_up_to_date"])
        self.assertEqual(response["config_version"], self.obox.config_version)

    def test_sync_returns_exactly_the_config_response(self):
        response = self._rpc("/obox/sync", self._credentials(state={"ip": "10.0.0.9"}))

        self.obox.invalidate_recordset()
        self.assertEqual(response, self.obox._config_response())
        self.assertFalse(response["config_up_to_date"])

    def test_sync_returns_exactly_the_config_response_once_up_to_date(self):
        response = self._rpc("/obox/sync", self._credentials(
            state={"ip": "10.0.0.9", "config_version": self.obox.config_version},
        ))

        self.obox.invalidate_recordset()
        self.assertEqual(response, self.obox._config_response())
        self.assertEqual(response, {"config_up_to_date": True})

    def test_sync_says_nothing_more_once_the_box_echoes_the_version(self):
        version = self.obox.config_version
        response = self._rpc("/obox/sync", self._credentials(
            state={"ip": "10.0.0.9", "config_version": version},
        ))
        self.assertTrue(response["config_up_to_date"])
        self.assertNotIn("config", response)

    def test_a_bad_token_is_rejected(self):
        with self.assertRaises(Exception):
            self._rpc("/obox/sync", {
                "serial_number": "TEST",
                "token": "wrong",
                "state": {"ip": "10.0.0.9"},
            })


class TestOboxSyncRequest(CommonOboxTest):

    def setUp(self):
        super().setUp()
        self.obox.platform = "android"
        self.obox.services = ["odoo", "sync"]
        self.env["obox.queue"].search([("obox_id", "=", self.obox.id)]).unlink()

    def _pending(self):
        return self.env["obox.queue"].search([
            ("obox_id", "=", self.obox.id),
            ("action_type", "=", "request_sync"),
            ("status", "=", "pending"),
        ])

    def test_an_odoo_rename_queues_one_action(self):
        self.obox_printer.name = "Caisse 2"

        self.assertEqual(len(self._pending()), 1)

    def test_a_second_rename_reuses_the_pending_action(self):
        """The Obox fetches its actions on its own, so the one still waiting
        covers the second rename: no second action, and no error either."""
        self.obox_printer.name = "Caisse 2"
        first = self._pending()

        self.obox_scale.name = "Balance 2"

        self.assertEqual(self._pending(), first)

    def test_a_rename_while_the_box_is_busy_asks_for_nothing_more(self):
        self.obox_printer.name = "Caisse 2"
        self.obox.get_next_actions()  # the Obox took it, it is now processing

        self.obox_scale.name = "Balance 2"

        self.assertFalse(self._pending())

    def test_a_rename_the_box_reported_asks_for_nothing(self):
        self.obox.with_context(obox_sync=True).device_ids[0].name = "From the box"

        self.assertFalse(self._pending())
