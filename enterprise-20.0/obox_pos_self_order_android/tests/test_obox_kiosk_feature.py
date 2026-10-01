import odoo.tests

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@odoo.tests.tagged("post_install", "-at_install")
class TestOboxKioskFeature(SelfOrderCommonTest):

    def setUp(self):
        super().setUp()
        self.env["pos.config"].search([
            ("id", "!=", self.pos_config.id),
            ("self_ordering_mode", "=", "kiosk"),
        ]).self_ordering_mode = "nothing"
        self.obox = self.env["obox.obox"].create({
            "name": "Test Obox",
            "serial_number": "KIOSK-TEST",
            "state": "02_paired",
            "token": "dummy",
            "services": ["odoo", "kiosk"],
        })

    def test_no_kiosk_config_no_kiosk_feature(self):
        self.assertEqual(self.pos_config.self_ordering_mode, "consultation")
        self.assertNotIn("kiosk", self.obox._get_obox_features())

    def test_a_kiosk_config_declares_the_feature(self):
        self.pos_config.self_ordering_mode = "kiosk"
        self.assertIn("kiosk", self.obox._get_obox_features())

    def test_the_kiosk_detail_lists_the_config_with_its_url(self):
        self.pos_config.self_ordering_mode = "kiosk"
        detail = self.obox._get_obox_feature_details("kiosk")
        kiosks = detail["kiosk"]
        self.assertIn(self.pos_config.id, [kiosk["id"] for kiosk in kiosks])
        kiosk = next(k for k in kiosks if k["id"] == self.pos_config.id)
        self.assertEqual(kiosk["name"], self.pos_config.name)
        self.assertTrue(kiosk["url"])
        self.assertEqual(kiosk["timezone"], self.pos_config.company_id.tz)

    def test_a_kiosk_config_is_not_listed_in_point_of_sale(self):
        self.pos_config.self_ordering_mode = "kiosk"
        detail = self.obox._get_obox_feature_details("point_of_sale")
        self.assertNotIn(self.pos_config.id, [pos["id"] for pos in detail["point_of_sale"]])

    def test_a_non_kiosk_config_is_listed_in_point_of_sale(self):
        detail = self.obox._get_obox_feature_details("point_of_sale")
        self.assertIn(self.pos_config.id, [pos["id"] for pos in detail["point_of_sale"]])

    def test_the_config_features(self):
        self.pos_config.self_ordering_mode = "kiosk"
        config = self.obox.config
        self.assertIn("kiosk", config["features"])

    def test_an_obox_supports_kiosk_when_it_advertises_the_service(self):
        self.assertTrue(self.obox.supports_kiosk)

        self.obox.services = ["odoo"]
        self.assertFalse(self.obox.supports_kiosk)

    def test_opening_the_kiosk_without_assigned_obox_returns_the_url_action(self):
        self.pos_config.self_ordering_mode = "kiosk"

        action = self.pos_config.action_open_wizard()

        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertFalse(self.env["obox.queue"].search([("action_type", "=", "open_kiosk")]))

    def test_opening_the_kiosk_queues_an_action_on_the_assigned_obox(self):
        self.pos_config.write({
            "self_ordering_mode": "kiosk",
            "self_ordering_obox_id": self.obox.id,
        })

        action = self.pos_config.action_open_wizard()

        self.assertEqual(action["tag"], "display_notification")
        self.assertIn(self.obox.name, action["params"]["message"])
        queued = self.env["obox.queue"].search([("action_type", "=", "open_kiosk")])
        self.assertEqual(queued.obox_id, self.obox)
        self.assertEqual(queued.payload["url"], "/odoo/open_kiosk")
        self.assertEqual(queued.payload["payload"]["url"], self.pos_config.get_kiosk_url())
        self.assertEqual(
            queued.payload["payload"]["timezone"], self.pos_config.company_id.tz,
        )
